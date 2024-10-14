from django.shortcuts import redirect
from rest_framework import viewsets, parsers, mixins, decorators, status, exceptions

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
from .serializers import FileCreateSerializer, FileSerializer, DossierSerializer, ImageSerializer, JobSerializer
from .utils import Pagination, Ordering, Response
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, Filter, BaseCSVFilter, ChoiceFilter
import django_filters.rest_framework as filters
from stixify.worker.tasks import new_task
from drf_spectacular.utils import extend_schema, extend_schema_view

import textwrap

# Create your views here.
@extend_schema_view(
    list=extend_schema(
        summary="Search and retrieve a list of uploaded Files",
        description="This endpoint allows you to search for Files you've uploaded. This endpoint is particularly useful if you want to download the original File uploaded or find the Report object created for the uploaded File so you can retrieve the objects created for it.",
    ),
    retrieve=extend_schema(
        summary="Get a File by ID",
        description="This endpoint will return information for a specific File using its ID.",
        parameters=[
            OpenApiParameter('file_id', location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the File."),
        ],
    ),
    destroy=extend_schema(
        summary="Delete a File by ID",
        description="This endpoint will delete a File using its ID. IMPORTANT: this request will also delete the Report SDO, and all other SROs and SDOs created during processing for this File. SCOs will remain because they often have relationships to other objects.",
    ),
    create=extend_schema(
        summary="Upload a new File to be processed into STIX object",
        description="Upload a file to be processed by Stixify. IMPORTANT: files cannot be modified once uploaded. If you need to reprocess a file, you must upload it again.\n\nThe response will contain the Job information, including the Job `id`. This can be used with the GET Jobs by ID endpoint to monitor the status of the Job."
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
        
    def perform_create(self, serializer):
        return super().perform_create(serializer)
        
    @extend_schema(responses={200: JobSerializer}, request=FileCreateSerializer)
    def create(self, request, *args, **kwargs):
        serializer = FileCreateSerializer(data=request.data)
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
            Whan a file is uploaded it is converted to markdown using [file2txt](https://github.com/muchdogesec/file2txt/) which is subsequently used to make extractions from. This endpoint will return that output.\n\n
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
    def markdown(self, request, *args, **kwargs):
        obj: File = self.get_object()
        if not obj.markdown_file:
            return Response("No markdown file", status=status.HTTP_404_NOT_FOUND)
        return redirect(obj.markdown_file.url, permanent=True)
    
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
        description="This endpoint will return a list of all Dossiers created and information about them.",
    ),
    create=extend_schema(
        summary="Create a New Dossier",
        description=textwrap.dedent(
            """
            This endpoint allows you create a Dossier you can use to group Reports together.\n\n
            \n\n
            The following key/values are accepted in the body of the request:\n\n
            * `name` (required, string): up to 128 characters
            * `description` (optional, string): up to 512 characters
            * `created_by_ref` (required, STIX Identity Object): This is a full STIX Identity JSON. e.g. {"type":"identity","spec_version":"2.1","id":"identity--9779a2db-f98c-5f4b-8d08-8ee04e02dbb5","created":"2020-01-01T00:00:00.000Z","modified":"2020-01-01T00:00:00.000Z","name":"dogesec","description":"https://github.com/muchdogsec/","identity_class":"organization","sectors":["technology"],"contact_information":"https://www.dogesec.com/contact/","object_marking_refs":["marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487","marking-definition--97ba4e8b-04f6-57e8-8f6e-3a0f0a7dc0fb"]}
            * `tlp_level` (required, TLP level): options are; `clear`, `green`, `amber`, `amber+strict`, or `red`
            * `labels` (required, array of string): a list of labels for the Dossier. Useful to find it in search. e.g. `["label1","label2"]`
            """
        ),
    ),
    partial_update=extend_schema(
        summary="Update a Dossier",
        description="This endpoint allows you update a Dossier. Use this endpoint to add or remove reports from a Dossier",
    ),
    retrieve=extend_schema(
        summary="Get a Dossier by ID",
        description="This endpoint will return information for a specific Dossier using its ID.",
        parameters=[
            OpenApiParameter('dossier_id', location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the Dossier."),
        ],
    ),
    destroy=extend_schema(
        summary="Delete a Dossier by ID",
        description="This endpoint will delete a Dossier using its ID. This request will not affect any Reports or the data linked to the Reports attached to the deleted Dossier.",
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

    ordering_fields = ["name", "created", "modified"]
    ordering = "modified_descending"
    filter_backends = [DjangoFilterBackend, Ordering]

    class filterset_class(FilterSet):
        name = Filter(lookup_expr='search', label="Filter results by the `name` of the Dossier. Search is a wildcard so `threat` will match any name that contains the string `threat`.")
        labels = Filter(lookup_expr='search', label="Filter results by the `labels` of the Dossier.")
        description = Filter(lookup_expr='search', label="Filter results by the `description` of the Dossier. Search is a wildcard so `threat` will match any description that contains the string `threat`. ")
        created_by_ref = filters.MultipleChoiceFilter(label="Filter results by the Identity `id` that created the Dossier. e.g. `identity--9779a2db-f98c-5f4b-8d08-8ee04e02dbb5`. (FIELD IS MULTI STRING).")

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
        parameters=ArangoDBHelper.get_schema_operation_parameters()+[
            OpenApiParameter(
                "include_txt2stix_notes",
                type=bool,
                default=False,
                description="txt2stix creates 3 STIX note Objects that provide information about the processing job. This data is only really helpful for debugging issues, but not for intelligence sharing. Setting this parameters value to `true` will include these STIX note Objects in the response. Most of the time you want to set this parameter to `false` (the default value).",
            )
        ],
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
                'include_txt2stix_notes': helper.query_as_bool('include_txt2stix_notes', False)
                
        }
        query = """
            FOR doc in @@collection
            FILTER doc._stixify_report_id == @report_id AND (doc.type != "note" OR @include_txt2stix_notes)
            
            LIMIT @offset, @count
            RETURN KEEP(doc, KEYS(doc, TRUE))
        """
        return helper.execute_query(query, bind_vars=bind_vars)
