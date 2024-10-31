from django.shortcuts import redirect
from rest_framework import viewsets, parsers, mixins, decorators, status, exceptions
from django.http import HttpResponse, FileResponse

from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes

import typing
from django.conf import settings

from stixify.web.arango_based_views.arango_helpers import ArangoDBHelper

from stixify.web import serializers
from stixify.web.autoschema import DEFAULT_400_ERROR, DEFAULT_404_ERROR
if typing.TYPE_CHECKING:
    from stixify import settings
from .models import File, Dossier, FileImage, Job
from .serializers import FileSerializer, DossierSerializer, ImageSerializer, JobSerializer
from .utils import Pagination, Ordering, Response
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, Filter, BaseCSVFilter, ChoiceFilter
import django_filters.rest_framework as filters
from stixify.worker.tasks import new_task
from drf_spectacular.utils import extend_schema, extend_schema_view

import textwrap
import mistune, hyperlink
from mistune.renderers.markdown import MarkdownRenderer
from mistune.util import unescape
class MarkdownImageReplacer(MarkdownRenderer):
    def __init__(self, request, queryset):
        self.request = request
        self.queryset = queryset
        super().__init__()
    def image(self, token: dict[str, dict], state: mistune.BlockState) -> str:
        src = token['attrs']['url']
        if not hyperlink.parse(src).absolute:
            try:
                token['attrs']['url'] = self.request.build_absolute_uri(self.queryset.get(name=src).file.url)
            except Exception as e:
                pass
        return super().image(token, state)
    
    def codespan(self, token: dict[str, dict], state: mistune.BlockState) -> str:
        token['raw'] = unescape(token['raw'])
        return super().codespan(token, state)
# Create your views here.
@extend_schema_view(
    list=extend_schema(
        summary="Search and retrieve a list of uploaded Files",
        description=textwrap.dedent(
            """
            This endpoint allows you to search for Files you've uploaded. This endpoint is particularly useful if you want to download the original File uploaded or find the Report object created for the uploaded File so you can retrieve the objects created for it.
            """
        ),
    ),
    retrieve=extend_schema(
        summary="Get a File by ID",
        description=textwrap.dedent(
            """
            This endpoint will return information for a specific File using its ID.
            """
        ),
        parameters=[
            OpenApiParameter('file_id', location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the File."),
        ],
    ),
    destroy=extend_schema(
        summary="Delete a File by ID",
        description=textwrap.dedent(
            """
            This endpoint will delete a File using its ID. It will also delete the markdown, images and original file stored for this File.

            IMPORTANT: this request does NOT delete the Report SDO created from the file, or any other STIX objects created from this file during extractions. To delete these, use the delete report endpoint.
            """
        ),
    ),
    create=extend_schema(
        summary="Upload a new File",
        description=textwrap.dedent(
            """
            Upload a file to be processed by Stixify. During processing a file is turned into markdown by [file2txt](https://github.com/muchdogesec/file2txt/), which is then passed to [txt2stix](https://github.com/muchdogesec/txt2stix/) to .

            The following key/values are accepted in the body of the request:

            * `file` (required): Full path to the file to be converted. The mimetype of the file uploaded must match that expected by the `mode` selected.
            * `profile_id` (required): a valid profile ID to define how the post should be processed. You can add a profile using the POST Profile endpoint.
            * `mode` (required): How the File should be processed. Options are:
                * `txt`: Filetypes supported (mime-type): `txt` (`text/plain`)
                * `image`: Filetypes supported (mime-type): `jpg` (`image/jpg`), `.jpeg` (`image/jpeg`), `.png` (`image/png`), `.webp` (`image/webp`)
                * `csv`: Filetypes supported (mime-type): `csv` (`text/csv`)
                * `html`: Filetypes supported (mime-type): `html` (`text/html`)
                * `html_article`: same as `html` but only considers the article on the page, good for blog posts. Filetypes supported (mime-type): `html` (`text/html`)
                * `word`: Filetypes supported (mime-type): `docx` (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`), `doc` (`application/msword`)
                * `pdf`: Filetypes supported (mime-type): `pdf` (`application/pdf`)
                * `powerpoint`: Filetypes supported (mime-type): `ppt` (`application/vnd.ms-powerpoint`), `.jpeg` (`application/vnd.openxmlformats-officedocument.presentationml.presentation`)
            * `name` (required): This will be used as the name value of the STIX Report object generated
            * `identity` (optional): This will be used as the `created_by_ref` for all created SDOs and SROs. This is a full STIX Identity JSON. e.g. `{"type":"identity","spec_version":"2.1","id":"identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15","name":"Dummy Identity"}`. If no value is passed, [the Stixify identity object will be used](https://raw.githubusercontent.com/muchdogesec/stix4doge/refs/heads/main/objects/identity/stixify.json).
            * `tlp_level` (optional): This will be assigned to all SDOs and SROs created. Stixify uses TLPv2. Options are:
                * `red`
                * `amber+strict`
                * `amber`
                * `green`
                * `clear`
            * `confidence` (optional): Will be added to the `confidence` value of the Report SDO created. A value between 0-100. `0` means confidence unknown. `1` is the lowest confidence score, `100` is the highest confidence score.
            * `labels` (optional): Will be added to the `labels` of the Report SDO created.

            Files cannot be modified once uploaded. If you need to reprocess a file, you must upload it again.

            The response will contain the Job information, including the Job `id`. This can be used with the GET Jobs by ID endpoint to monitor the status of the Job.
            """
        ),
    ),
)
class FileView(
    mixins.CreateModelMixin, mixins.DestroyModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    pagination_class = Pagination("files")
    serializer_class = FileSerializer
    parser_classes = [parsers.MultiPartParser]
    openapi_tags = ["Files"]
    lookup_url_kwarg = "file_id"
    openapi_path_params = [
        OpenApiParameter(
            lookup_url_kwarg, location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the File."
        )
    ]

    ordering_fields = ["name", "created"]
    ordering = "created_descending"
    filter_backends = [DjangoFilterBackend, Ordering]

    def get_queryset(self):
        return File.objects.all()


    class filterset_class(FilterSet):
        id = filters.BaseCSVFilter(help_text="Filter the results by the id of the file", lookup_expr="in")
        # report_ids = BaseCSVFilter(label="search by report IDs", field_name="report_id")
        report_id = filters.BaseInFilter(help_text="Filter results by the STIX Report object ID generated when processing the File")
        name = Filter(lookup_expr='search', help_text="Filter results by the `name` value assigned when uploading the File. Search is a wildcard so `threat` will match any name that contains the string `threat`.")
        mode = filters.BaseInFilter(help_text="Filter results by the `mode` value assigned when uploading the File")
        # dossier_id = filters.BaseInFilter(field_name='dossiers', help_text="The Dossier ID(s) you want to add the generated Report for this File to.")
        
    def perform_create(self, serializer):
        return super().perform_create(serializer)
        
    @extend_schema(responses={200: JobSerializer}, request=FileSerializer)
    def create(self, request, *args, **kwargs):
        serializer = FileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        temp_file = request.FILES['file']
        file_instance = serializer.save(mimetype=temp_file.content_type)
        job_instance =  Job.objects.create(file=file_instance)
        job_serializer = JobSerializer(job_instance)
        new_task(job_instance, file_instance)
        return Response(job_serializer.data)
    
    @extend_schema(
        responses=None,
        summary="Get the processed markdown for a File",
        description=textwrap.dedent(
            """
            Whan a file is uploaded it is converted to markdown using [file2txt](https://github.com/muchdogesec/file2txt/) which is subsequently used to make extractions from. This endpoint will return that output.
            
            This endpoint is useful for debugging issues in extractions when you think there could be an issue with the content being passed to the extractors.
            """
        ),
        parameters=[
            OpenApiParameter(
                name="Location",
                type=OpenApiTypes.URI,
                location=OpenApiParameter.HEADER,
                description="redirect location of markdown file",
                response=[301],
            )
        ],
    )
    @decorators.action(detail=True, methods=["GET"])
    def markdown(self, request, *args, file_id=None, **kwargs):
        obj: File = self.get_object()
        if not obj.markdown_file:
            return Response("No markdown file", status=status.HTTP_404_NOT_FOUND)
        modify_links = mistune.create_markdown(escape=False, renderer=MarkdownImageReplacer(self.request, FileImage.objects.filter(report__id=file_id)))
        return FileResponse(streaming_content=modify_links(obj.markdown_file.read().decode()), content_type='text/markdown', filename=f'{obj.name}-markdown.md')
    
    @extend_schema(
            responses={200: ImageSerializer(many=True), 404: DEFAULT_404_ERROR, 400: DEFAULT_400_ERROR},
            filters=False,
            summary="Retrieve images found in a File",
            description=textwrap.dedent(
            """
            When [file2txt](https://github.com/muchdogesec/file2txt/) processes a file it will extract all images from the file and store them locally. You can see these images referenced in the markdown produced (see File markdown endpoint). This endpoint lists the image files found in the File selected.
            """
        ),
    )
    @decorators.action(detail=True, pagination_class=Pagination("images"))
    def images(self, request, file_id=None, image=None):
        queryset = FileImage.objects.filter(report__id=file_id).order_by('name')
        paginator = Pagination('images')

        page = paginator.paginate_queryset(queryset, request, self)

        if page is not None:
            serializer = ImageSerializer(page, many=True, context=dict(request=request))
            return paginator.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

@extend_schema_view(
    list=extend_schema(
        summary="Search and retrieve a list of created Dossiers",
        description=textwrap.dedent(
            """
            This endpoint will return a list of all Dossiers created and information about them.
            """
        ),
    ),
    create=extend_schema(
        summary="Create a New Dossier",
        description=textwrap.dedent(
            """
            This endpoint allows you create a Dossier you can use to group Reports together.

            The following key/values are accepted in the body of the request:
            * `name` (required, string): up to 128 characters
            * `description` (optional, string): up to 512 characters
            * `created_by_ref` (required, STIX Identity Object): This is a full STIX Identity JSON. e.g. `{"type":"identity","spec_version":"2.1","id":"identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15","name":"Dummy Identity"}`. If no value is passed, [the Stixify identity object will be used](https://raw.githubusercontent.com/muchdogesec/stix4doge/refs/heads/main/objects/identity/stixify.json).
            * `tlp_level` (required, TLP level): options are; `clear`, `green`, `amber`, `amber+strict`, or `red`
            * `labels` (required, array of string): a list of labels for the Dossier. Useful to find it in search. e.g. `["label1","label2"]`
            """
        ),
    ),
    partial_update=extend_schema(
        summary="Update a Dossier",
        description=textwrap.dedent(
            """
            This endpoint allows you update a Dossier. Use this endpoint to add or remove reports from a Dossier
            """
        ),
    ),
    retrieve=extend_schema(
        summary="Get a Dossier by ID",
        description=textwrap.dedent(
            """
            This endpoint will return information for a specific Dossier using its ID.
            """
        ),
        parameters=[
            OpenApiParameter('dossier_id', location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the Dossier."),
        ],
    ),
    destroy=extend_schema(
        summary="Delete a Dossier by ID",
        description=textwrap.dedent(
            """
            This endpoint will delete a Dossier using its ID. This request will not affect any Reports or the data linked to the Reports attached to the deleted Dossier.
            """
        ),
        parameters=[
            OpenApiParameter('dossier_id', location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the Dossier."),
        ],
    ),
)
class DossierView(
    mixins.CreateModelMixin, mixins.DestroyModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    pagination_class = Pagination("dossiers")
    serializer_class = DossierSerializer
    openapi_tags = ["Dossiers"]
    lookup_url_kwarg = "dossier_id"
    openapi_path_params = [
        OpenApiParameter(
            lookup_url_kwarg, location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the Dossier."
        )
    ]

    ordering_fields = ["name", "created", "modified"]
    ordering = "modified_descending"
    filter_backends = [DjangoFilterBackend, Ordering]

    class filterset_class(FilterSet):
        created_by_ref = filters.BaseInFilter(field_name='created_by_ref__id', label="Filter results by the Identity `id` that created the Dossier. e.g. `identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15`.")

    def get_queryset(self):
        return Dossier.objects.all()


@extend_schema_view(
    list=extend_schema(
        summary="Search and retrieve a list of Jobs",
        description="Jobs track the status of File upload, conversion of the File into markdown and the extraction of the data from the text. For every new File added a job will be created. The `id` of a Job is printed in the POST responses, but you can use this endpoint to search for the `id` again, if required.",
    ),
    retrieve=extend_schema(
        summary="Get a job by ID",
        description="Using a Job ID you can retrieve information about its state via this endpoint. This is useful to see if a Job is still processing, if an error has occurred (and at what stage), or if it has completed.",
        parameters=[
            OpenApiParameter('job_id', location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the Job."),
        ],
    ),
)
class JobView(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    openapi_tags = ["Jobs"]
    pagination_class = Pagination("jobs")
    serializer_class = JobSerializer
    lookup_url_kwarg = "job_id"

    ordering_fields = ["state", "run_datetime", "completion_time"]
    ordering = "run_datetime_ascending"
    filter_backends = [DjangoFilterBackend, Ordering]

    def get_queryset(self):
        return Job.objects.all()

    class filterset_class(FilterSet):
        # report_ids = BaseCSVFilter(label="search by report IDs", field_name="report_id")
        report_id = Filter('file__report_id', label="Filter Jobs by Report `id`")
        file_id = Filter('file_id', label="Filter Jobs by File `id`")



@extend_schema_view(
    list=extend_schema(
        summary="Search for Report objects created from Files",
        description="Search for Report objects created from Files",
    ),
    retrieve=extend_schema(
        summary="Get a Report object using its ID",
        description="Get a Report object using its ID",
    ),
    objects=extend_schema(
        summary="Get all objects linked to a Report ID",
        description="This endpoint returns all objects that were extracted and created for the File linked to this report.",
    ),
)
class ReportView(viewsets.ViewSet):
    openapi_tags = ["Reports"]
    lookup_url_kwarg = "report_id"
    openapi_path_params = [
        OpenApiParameter(
            lookup_url_kwarg, location=OpenApiParameter.PATH, description="The `id` of the Report."
        )
    ]

    @extend_schema()
    def retrieve(self, request, *args, **kwargs):
        report_id = kwargs.get(self.lookup_url_kwarg)
        reports = ArangoDBHelper(settings.VIEW_NAME, request).get_report_by_id(
            report_id
        )
        if not reports:
            raise exceptions.NotFound(
                detail=f"report object with id `{report_id}` - not found"
            )
        return Response(reports[-1])

    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters(),
    )
    def list(self, request, *args, **kwargs):
        return ArangoDBHelper(settings.VIEW_NAME, request).get_reports()
    
    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters(),
    )
    @decorators.action(methods=["GET"], detail=True)
    def objects(self, request, *args, report_id=..., **kwargs):
        return self.get_report_objects(report_id)
    

    # @extend_schema()
    # def destroy(self, request, *args, **kwargs):
    #     report_id = kwargs.get(self.lookup_url_kwarg)
    #     self.remove_report(report_id)
    #     File.objects.filter(report_id=report_id).delete()
    #     return Response(status=status.HTTP_204_NO_CONTENT)
    
    def remove_report(self, report_id):
        helper = ArangoDBHelper(settings.VIEW_NAME, self.request)

        bind_vars = {
                "@collection": helper.collection,
                'report_id': report_id,
        }
        query = """
            FOR doc in @@collection
            FILTER doc._stixify_report_id == @report_id
            RETURN doc._id
        """
        collections: dict[str, list] = {}
        out = helper.execute_query(query, bind_vars=bind_vars, paginate=False)
        for key in out:
            collection, key = key.split('/', 2)
            collections[collection] = collections.get(collection, [])
            collections[collection].append(key)

        deletion_query = """
            FOR _key in @objects
            REMOVE {_key} IN @@collection
            RETURN _key
        """

        for collection, objects in collections.items():
            bind_vars = {
                "@collection": collection,
                "objects": objects,
            }
            helper.execute_query(deletion_query, bind_vars, paginate=False)

    def get_report_objects(self, report_id):
        helper = ArangoDBHelper(settings.VIEW_NAME, self.request)
        bind_vars = {
                "@collection": settings.VIEW_NAME,
                'report_id': report_id,                
        }
        query = """
            FOR doc in @@collection
            FILTER doc._stixify_report_id == @report_id
            
            LIMIT @offset, @count
            RETURN KEEP(doc, KEYS(doc, TRUE))
        """
        return helper.execute_query(query, bind_vars=bind_vars)
