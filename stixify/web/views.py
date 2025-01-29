import io
import uuid
from rest_framework import viewsets, parsers, mixins, decorators, status, exceptions, request, validators
from django.http import FileResponse, HttpRequest, HttpResponseNotFound

from django.db.models import F, Value, CharField, Func

from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes

import typing
from django.conf import settings

from dogesec_commons.objects.helpers import ArangoDBHelper

from stixify.web.autoschema import DEFAULT_400_ERROR, DEFAULT_404_ERROR
if typing.TYPE_CHECKING:
    from stixify import settings
from .models import TLP_LEVEL_STIX_ID_MAPPING, File, Dossier, FileImage, Job, TLP_Levels
from .serializers import FileSerializer, DossierSerializer, ImageSerializer, JobSerializer
from .utils import Response
from dogesec_commons.utils import Pagination, Ordering
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, Filter
import django_filters.rest_framework as filters
from stixify.worker.tasks import new_task
from drf_spectacular.utils import extend_schema, extend_schema_view

## markdown helper
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
## markdown helper ends

# Create your views here.
@extend_schema_view(
    list=extend_schema(
        summary="Search and retrieve a list of uploaded Files",
        description=textwrap.dedent(
            """
            This endpoint allows you to search for Files you've uploaded. This endpoint is particularly useful if you want to download the original File uploaded or find the Report object created for the uploaded File so you can retrieve the objects created for it.
            """
        ),
        responses={200: FileSerializer, 400: DEFAULT_400_ERROR},
    ),
    retrieve=extend_schema(
        summary="Get a File by ID",
        description=textwrap.dedent(
            """
            This endpoint will return information for a specific File using its ID.
            """
        ),
        parameters=[
            OpenApiParameter('file_id', location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the File (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`)."),
        ],
        responses={200: FileSerializer, 400: DEFAULT_400_ERROR, 404: DEFAULT_404_ERROR},

    ),
    destroy=extend_schema(
        summary="Delete a File by ID",
        description=textwrap.dedent(
            """
            This endpoint will delete a File using its ID. It will also delete the markdown, images and original file stored for this File.

            IMPORTANT: this request does NOT delete the Report SDO created from the file, or any other STIX objects created from this file during extractions. To delete these, use the delete report endpoint.
            """
        ),
        responses={200: FileSerializer, 404: DEFAULT_404_ERROR},
    ),
    create=extend_schema(
        responses={201: JobSerializer, 400: DEFAULT_400_ERROR},
        summary="Upload a new File",
        description=textwrap.dedent(
            """
            Upload a file to be processed by Stixify. During processing a file is turned into markdown by [file2txt](https://github.com/muchdogesec/file2txt/), which is then passed to [txt2stix](https://github.com/muchdogesec/txt2stix/) to .

            The following key/values are accepted in the body of the request:

            * `file` (required): Full path to the file to be converted. The mimetype of the file uploaded must match that expected by the `mode` selected.
            * `report_id` (optional): Only pass a UUIDv4. It will be use to generate the STIX Report ID, e.g. `report--<UUID>`. If not passed, this file will be randomly generated.
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
        name = Filter(lookup_expr='search', help_text="Filter results by the `name` value assigned when uploading the File. Search is a wildcard so `threat` will match any name that contains the string `threat`.")
        mode = filters.BaseInFilter(help_text="Filter results by the `mode` value assigned when uploading the File")
        created_max = filters.DateTimeFilter('created', lookup_expr='gte', help_text='Maximum value of `created` value to filter by in format `YYYY-MM-DD`.')
        created_min = filters.DateTimeFilter('created', lookup_expr='lte', help_text='Minimum value of `created` value to filter by in format `YYYY-MM-DD`.')
        profile_id = filters.Filter(help_text="Filter profiles by the `id` of the Profile. e.g. `7ac37275-9137-4648-80ad-a9aa200b73f0`")
        
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
        responses={200:{}, 404: DEFAULT_404_ERROR},
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
            return HttpResponseNotFound("No markdown file")
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
        queryset = self.get_object().images.order_by('name')
        paginator = Pagination('images')

        page = paginator.paginate_queryset(queryset, request, self)

        if page is not None:
            serializer = ImageSerializer(page, many=True, context=dict(request=request))
            return paginator.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
            responses={200:{}, 404: DEFAULT_404_ERROR},
            summary="Get summary of the file content",
            description=textwrap.dedent(
            """
            If `ai_summary_provider` was enabled, this endpoint will return a summary of the report. This is useful to get a quick understanding of the contents of the report.

            The prompt used to generate the summary can be seen in [dogesec_commons here](https://github.com/muchdogesec/dogesec_commons/blob/main/dogesec_commons/stixifier/summarizer.py).

            If you want a summary but `ai_summary_provider` was not enabled during processing, you will need to process the file again.
            """
        ),
    )
    @decorators.action(methods=["GET"], detail=True)
    def summary(self, request, file_id=None):
        obj = self.get_object()
        if not obj.summary:
            raise exceptions.NotFound(f"No Summary for post")
        return FileResponse(streaming_content=io.BytesIO(obj.summary.encode()), content_type='text/markdown', filename='summary.md')

@extend_schema_view(
    list=extend_schema(
        summary="Search and retrieve a list of created Dossiers",
        description=textwrap.dedent(
            """
            This endpoint will return a list of all Dossiers created and information about them.
            """
        ),
        responses={200: DossierSerializer, 400: DEFAULT_400_ERROR},
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
        responses={201: DossierSerializer, 400: DEFAULT_400_ERROR},
    ),
    partial_update=extend_schema(
        summary="Update a Dossier",
        description=textwrap.dedent(
            """
            This endpoint allows you update a Dossier. Use this endpoint to add or remove reports from a Dossier
            """
        ),
        responses={200: DossierSerializer, 400: DEFAULT_400_ERROR, 404: DEFAULT_404_ERROR},
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
        responses={200: DossierSerializer, 400: DEFAULT_400_ERROR, 404: DEFAULT_404_ERROR},
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
        responses={204: DossierSerializer, 404: DEFAULT_404_ERROR},
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
        name = Filter(lookup_expr='search', label="Filter results by the `name` of the Dossier. Search is a wildcard so `threat` will match any name that contains the string `threat`.")
        labels = Filter(field_name='labels_str', lookup_expr='search', label="Filter results by the `labels` of the Dossier.")
        description = Filter(lookup_expr='search', label="Filter results by the `description` of the Dossier. Search is a wildcard so `threat` will match any description that contains the string `threat`. ")
        created_by_ref = filters.BaseInFilter(field_name='created_by_ref__id', label="Filter results by the Identity `id` that created the Dossier. e.g. `identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15`.")

    def get_queryset(self):
        return Dossier.objects.all().annotate(
            labels_str=Func(
                F("labels"),
                Value(", "),  # The delimiter
                function="array_to_string",
                output_field=CharField(),
            )
        )


@extend_schema_view(
    list=extend_schema(
        summary="Search and retrieve a list of Jobs",
        description=textwrap.dedent(
            """
            Jobs track the status of File upload, conversion of the File into markdown and the extraction of the data from the text. For every new File added a job will be created. The `id` of a Job is printed in the POST responses, but you can use this endpoint to search for the `id` again, if required.
            """
        ),
        responses={200: JobSerializer, 400: DEFAULT_400_ERROR},
    ),
    retrieve=extend_schema(
        summary="Get a job by ID",
        description=textwrap.dedent(
            """
            Using a Job ID you can retrieve information about its state via this endpoint. This is useful to see if a Job is still processing, if an error has occurred (and at what stage), or if it has completed.
            """
        ),
        parameters=[
            OpenApiParameter('job_id', location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the Job."),
        ],
        responses={200: JobSerializer, 404: DEFAULT_404_ERROR},
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
        file_id = Filter('file_id', label="Filter Jobs by File `id`")


@extend_schema_view(
    list=extend_schema(
        summary="Search for Report objects created from Files",
        description=textwrap.dedent(
            """
            Search for Report objects created from Files
            """
        ),
    ),
    retrieve=extend_schema(
        summary="Get a Report object using its ID",
        description=textwrap.dedent(
            """
            Get a Report object using its ID
            """
        ),
    ),
    objects=extend_schema(
        summary="Get all objects linked to a Report ID",
        description=textwrap.dedent(
            """
            This endpoint returns all STIX objects that were extracted and created for the File linked to this report.
            """
        ),
    ),
    destroy=extend_schema(
        summary="Delete all STIX objects for a Report ID",
        description=textwrap.dedent(
            """
            This endpoint will delete a Report using its ID. It will also delete all the STIX objects extracted from the Report.

            IMPORTANT: this request does NOT delete the file this Report was generated from. To delete the file, use the delete file endpoint.
            """
        ),
    ),
)
class ReportView(viewsets.ViewSet):
    openapi_tags = ["Reports"]
    skip_list_view = True
    lookup_url_kwarg = "report_id"
    lookup_value_regex = r'report--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    openapi_path_params = [
        OpenApiParameter(
            lookup_url_kwarg, location=OpenApiParameter.PATH, type=dict(pattern=r'^report--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'), description="The `id` of the Report. e.g. `report--3fa85f64-5717-4562-b3fc-2c963f66afa6`."
        )
    ]

    @extend_schema()
    def retrieve(self, request, *args, **kwargs):
        report_id = kwargs.get(self.lookup_url_kwarg)
        report_id = self.validate_report_id(report_id)
        reports: Response = ArangoDBHelper(settings.VIEW_NAME, request).get_objects_by_id(
            self.fix_report_id(report_id)
        )
        if not reports.data:
            raise exceptions.NotFound(
                detail=f"report object with id `{report_id}` - not found"
            )
        return reports

    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters() + [
            OpenApiParameter('identity', description="Filter the result by only the reports created by this identity. Pass in the format `identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15`"),
            OpenApiParameter('name', description="Filter by the `name` of a report. Search is wildcard so `exploit` will match `exploited`, `exploits`, etc."),
            OpenApiParameter('tlp_level', description="", enum=[f[0] for f in TLP_Levels.choices]),
            OpenApiParameter('description', description="Filter by the content in a report `description` (which contains the markdown version of the report). Will search for descriptions that contain the value entered. Search is wildcard so `exploit` will match `exploited`, `exploits`, etc."),
            OpenApiParameter('labels', description="searches the `labels` property for the value entered. Search is wildcard so `exploit` will match `exploited`, `exploits`, etc."),
            OpenApiParameter('confidence_min', description="The minimum confidence score of a report `0` is no confidence, `1` is lowest, `100` is highest.", type=OpenApiTypes.NUMBER),
            OpenApiParameter('created_max', description="Maximum value of `created` value to filter by in format `YYYY-MM-DD`."),
            OpenApiParameter('created_min', description="Minimum value of `created` value to filter by in format `YYYY-MM-DD`."),
        ],
    )
    def list(self, request, *args, **kwargs):
        return self.get_reports()
    
    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters(),
    )
    @decorators.action(methods=["GET"], detail=True)
    def objects(self, request, *args, report_id=..., **kwargs):
        report_id = self.validate_report_id(report_id)
        return self.get_report_objects(self.fix_report_id(report_id))
    
    @classmethod
    def fix_report_id(self, report_id):
        if report_id.startswith('report--'):
            return report_id
        return "report--"+report_id
    
    @classmethod
    def validate_report_id(self, report_id:str):
        if not report_id.startswith('report--'):
            raise validators.ValidationError({self.lookup_url_kwarg: f'`{report_id}`: must be a valid STIX report id'})
        report_uuid = report_id.replace('report--', '')
        try:
            uuid.UUID(report_uuid)
        except Exception as e:
            raise validators.ValidationError({self.lookup_url_kwarg: f'`{report_id}`: {e}'})
        return report_uuid

    @extend_schema()
    def destroy(self, request, *args, **kwargs):
        report_id = kwargs.get(self.lookup_url_kwarg)
        report_id = self.validate_report_id(report_id)

        File.objects.filter(id=report_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @classmethod
    def remove_report(cls, report_id):
        helper = ArangoDBHelper(settings.VIEW_NAME, request.Request(HttpRequest()))
        report_id = cls.fix_report_id(report_id)
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

    def get_reports(self, id=None):
        helper = ArangoDBHelper(settings.VIEW_NAME, self.request)
        filters = []
        bind_vars = {
                "@collection": helper.collection,
                "type": 'report',
        }

        if q := helper.query_as_array('identity'):
            bind_vars['identities'] = q
            filters.append('FILTER doc.created_by_ref IN @identities')

        if tlp_level := helper.query.get('tlp_level'):
            bind_vars['tlp_level_stix_id'] = TLP_LEVEL_STIX_ID_MAPPING.get(tlp_level)
            filters.append('FILTER @tlp_level_stix_id IN doc.object_marking_refs')

        if q := helper.query.get('name'):
            bind_vars['name'] = q.lower()
            filters.append('FILTER CONTAINS(LOWER(doc.name), @name)')

        if q := helper.query.get('description'):
            bind_vars['description'] = q.lower()
            filters.append('FILTER CONTAINS(LOWER(doc.description), @description)')

        if term := helper.query.get('labels'):
            bind_vars['labels'] = term.lower()
            filters.append("FILTER doc.labels[? ANY FILTER CONTAINS(LOWER(CURRENT), @labels)]")

        if term := helper.query.get('confidence_min'):
            if term.replace('.', '').isdigit():
                bind_vars['confidence_min'] = float(term)
                filters.append("FILTER doc.confidence >= @confidence_min")

        if term := helper.query.get('created_max'):
            bind_vars['created_max'] = term
            filters.append("FILTER doc.created <= @created_max")
        if term := helper.query.get('created_min'):
            bind_vars['created_min'] = term
            filters.append("FILTER doc.created >= @created_min")

        query = """
            FOR doc in @@collection
            FILTER doc.type == @type AND doc._is_latest
            // <other filters>
            @filters
            // </other filters>
            LIMIT @offset, @count
            RETURN KEEP(doc, KEYS(doc, true))
        """
        return helper.execute_query(query.replace('@filters', '\n'.join(filters)), bind_vars=bind_vars)

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
