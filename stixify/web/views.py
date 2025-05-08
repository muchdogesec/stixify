from functools import reduce
import io
import logging
import operator
import re
import uuid
from django import forms
from rest_framework import viewsets, parsers, mixins, decorators, status, exceptions, request, validators
from django.http import FileResponse, HttpRequest, HttpResponseNotFound
from django.utils.text import slugify
from dogesec_commons.objects.helpers import OBJECT_TYPES
from django.db.models import F, Value, CharField, Func, Q

from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from stix2arango.services import ArangoDBService

import typing
from django.conf import settings

from dogesec_commons.objects.helpers import ArangoDBHelper

from stixify.web.autoschema import DEFAULT_400_ERROR, DEFAULT_404_ERROR
if typing.TYPE_CHECKING:
    from stixify import settings
from .models import TLP_LEVEL_STIX_ID_MAPPING, File, FileImage, Job, TLP_Levels, JobState
from .serializers import FileSerializer, ImageSerializer, JobSerializer
from .utils import Response, MinMaxDateFilter
from dogesec_commons.utils import Pagination, Ordering
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, Filter
import django_filters.rest_framework as filters
from django_filters import fields as django_filters_fields
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

from drf_spectacular.views import SpectacularAPIView
from rest_framework.response import Response

class SchemaViewCached(SpectacularAPIView):
    _schema = None
    
    def _get_schema_response(self, request):
        version = self.api_version or request.version or self._get_version_parameter(request)
        if not self.__class__._schema:
            generator = self.generator_class(urlconf=self.urlconf, api_version=version, patterns=self.patterns)
            self.__class__._schema = generator.get_schema(request=request, public=self.serve_public)
        return Response(
            data=self.__class__._schema,
            headers={"Content-Disposition": f'inline; filename="{self._get_filename(request, version)}"'}
        )
    
incident_classification_types = ['other', 'apt_group', 'vulnerability', 'data_leak', 'malware', 'ransomware', 'infostealer', 'threat_actor', 'campaign', 'exploit', 'cyber_crime', 'indicators_of_compromise', 'ttps']

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
            OpenApiParameter('file_id', location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the File. This will be the same as the UUID part of the STIX report object create from the file. (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`)."),
        ],
        responses={200: FileSerializer, 400: DEFAULT_400_ERROR, 404: DEFAULT_404_ERROR},

    ),
    destroy=extend_schema(
        summary="Delete a File by ID",
        description=textwrap.dedent(
            """
            This endpoint will delete a File using its ID. It will also delete the markdown, images and original file stored for this File.

            IMPORTANT: this request WILL also delete any STIX objects created from this file.
            """
        ),
        responses={204: {}, 404: DEFAULT_404_ERROR},
    ),
    create=extend_schema(
        responses={201: JobSerializer, 400: DEFAULT_400_ERROR},
        summary="Upload a new File",
        description=textwrap.dedent(
            """
            Upload a file to be processed by Stixify. During processing a file is turned into markdown by [file2txt](https://github.com/muchdogesec/file2txt/), which is then passed to [txt2stix](https://github.com/muchdogesec/txt2stix/) to .

            Files cannot be modified once uploaded.

            If you need to reprocess a file, you must upload it again. If you have lost a copy of the original file that you want to re-process, you can re-download it using the `download_url` value in the GET Files response.

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
            lookup_url_kwarg, location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="The `id` of the File (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`)."
        )
    ]
    ordering_fields = ["name", "created"]
    ordering = "created_descending"
    filter_backends = [DjangoFilterBackend, Ordering, MinMaxDateFilter]
    minmax_date_fields = ["created"]

    def get_queryset(self):
        return File.objects.all()


    class filterset_class(FilterSet):
        id = filters.BaseCSVFilter(help_text="Filter the results by the id of the file (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`).", lookup_expr="in")
        name = Filter(lookup_expr='search', help_text="Filter results by the `name` value assigned when uploading the File. Search is a wildcard so `threat` will match any name that contains the string `threat`.")
        mode = filters.BaseInFilter(help_text="Filter results by the `mode` value assigned when uploading the File")
        profile_id = filters.Filter(help_text="Filter by the `id` of the Profile to only include files processed by entered Profile ID. e.g. `7ac37275-9137-4648-80ad-a9aa200b73f0`")
        job_state = filters.ChoiceFilter(field_name='job__state', help_text="Job state of the file", choices=JobState.choices)

        ai_describes_incident = filters.BooleanFilter(help_text="If `ai_content_check_provider` set in profile used to process report, AI will answer if file describes security incident. Default will show all reports, can filter those that only describe incident by setting to true.")
        ai_incident_classification = filters.MultipleChoiceFilter(choices=[(c, c) for c in incident_classification_types], help_text="If `ai_content_check_provider` set in profile used to process report, AI will attempt to classify security incident type (if file describes incident). Use this to filter by type AI reports.", method='ai_incident_classification_filter')
        
        def ai_incident_classification_filter(self, queryset, name, value):
            filter = reduce(operator.or_, [Q(ai_incident_classification__icontains=s) for s in value])
            return queryset.filter(filter)
        
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
        return Response(job_serializer.data, status=status.HTTP_201_CREATED)
    

    @extend_schema(
        summary="show the data .json produced by txt2stix",
        description="show the data .json produced by txt2stix",
        responses={200: dict},
    )
    @decorators.action(detail=True, methods=["GET"])
    def extractions(self, request, post_id=None, **kwargs):
        obj = self.get_object()
        return Response(obj.txt2stix_data or {})
    
    
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
    ordering = "run_datetime_descending"
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
            When a file is uploaded a STIX report object will be created for it. The file `id` will match the UUID part of the STIX report object (e.g. `report--UUID`).
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
            This endpoint returns all STIX objects that were extracted from the uploaded File linked to this report.
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
    
    SORT_PROPERTIES = [
        "created_descending",
        "created_ascending",
        "name_descending",
        "name_ascending",
        "confidence_descending",
        "confidence_ascending",
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
            OpenApiParameter('visible_to', description="Only show reports that are visible to the Identity `id` passed. e.g. passing `identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15` would only show reports created by that identity (with any TLP level) or reports created by another identity ID but only if they are marked with `TLP:CLEAR` or `TLP:GREEN`."),
            OpenApiParameter('name', description="Filter by the `name` of a report. Search is wildcard so `exploit` will match `exploited`, `exploits`, etc."),
            OpenApiParameter('tlp_level', description="Filter the results by TLP marking of the Report object (set at file upload time).", enum=[f[0] for f in TLP_Levels.choices]),
            OpenApiParameter('description', description="Filter by the content in a report `description` (which contains the markdown version of the report). Will search for descriptions that contain the value entered. Search is wildcard so `exploit` will match `exploited`, `exploits`, etc."),
            OpenApiParameter('labels', description="Searches the `labels` property of Report objects for the value entered. Search is wildcard so `exploit` will match `exploited`, `exploits`, etc."),
            OpenApiParameter('ai_incident_classification', style='form', explode=False, many=True, description="If `ai_content_check_provider` set in profile used to process report, AI will attempt to classify security incident type (if file describes incident). Use this to filter by type AI reports.", enum=incident_classification_types),
            OpenApiParameter('confidence_min', description="The minimum confidence score of a report `0` is no confidence, `1` is lowest, `100` is highest.", type=OpenApiTypes.NUMBER),
            OpenApiParameter('created_max', description="Maximum value of `created` value to filter by in format `YYYY-MM-DD`."),
            OpenApiParameter('created_min', description="Minimum value of `created` value to filter by in format `YYYY-MM-DD`."),
            OpenApiParameter('sort', description="Sort the results by selected property", enum=SORT_PROPERTIES),
        ],
    )
    def list(self, request, *args, **kwargs):
        return self.get_reports()
    

    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters() + [
            OpenApiParameter('visible_to', description="Only show reports that are visible to the Identity `id` passed. e.g. passing `identity--b1ae1a15-6f4b-431e-b990-1b9678f35e15` would only show reports created by that identity (with any TLP level) or reports created by another identity ID but only if they are marked with `TLP:CLEAR` or `TLP:GREEN`."),
            OpenApiParameter(
                "types",
                many=True,
                explode=False,
                description="Filter the results by one or more STIX Object types",
                enum=OBJECT_TYPES,
            ),
            OpenApiParameter('ignore_embedded_sro', type=bool, description="If set to `true` all embedded SROs are removed from the response."),
            
        ],
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

    @classmethod
    def remove_report(cls, report_id):
        db_service = ArangoDBService(
            settings.ARANGODB_DATABASE,
            [],
            [],
            create=False,
            username=settings.ARANGODB_USERNAME,
            password=settings.ARANGODB_PASSWORD,
            host_url=settings.ARANGODB_HOST_URL,
        )
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
            collections[collection].append(dict(_key=key))
        
        for collection, objects in collections.items():
            helper.db.collection(collection).delete_many(objects, silent=True)
            db_service.update_is_latest_several_chunked([object_key['_key'].split('+')[0] for object_key in objects], collection, collection.removesuffix('_vertex_collection').removesuffix('_edge_collection')+'_edge_collection')


    def get_sort_stmt(self, sort_options: 'list[str]', customs={}):
        finder = re.compile(r"(.+)_((a|de)sc)ending")
        sort_field = self.request.GET.get('sort')
        if sort_field not in sort_options:
            sort_field = sort_options[0]
        if m := finder.match(sort_field):
            field = m.group(1)
            direction = m.group(2).upper()
            if cfield := customs.get(field):
                return f"SORT {cfield} {direction}"
            return f"SORT doc.{field} {direction}"

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

        if q := helper.query.get('visible_to'):
            bind_vars['visible_to'] = q
            bind_vars['marking_visible_to_all'] = TLP_LEVEL_STIX_ID_MAPPING[TLP_Levels.GREEN], TLP_LEVEL_STIX_ID_MAPPING[TLP_Levels.CLEAR]
            filters.append('FILTER doc.created_by_ref == @visible_to OR @marking_visible_to_all ANY IN doc.object_marking_refs')

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

        if classifications := helper.query_as_array('ai_incident_classification'):
            bind_vars['classifications'] = ["txt2stix:"+x.lower().replace(' ', '_') for x in classifications]
            print(bind_vars['classifications'])
            filters.append('FILTER @classifications ANY IN doc.labels')

        query = """
            FOR doc in @@collection
            FILTER doc.type == @type AND doc._is_latest
            // <other filters>
            #more_filters
            // </other filters>
            #sort_statement
            LIMIT @offset, @count
            RETURN KEEP(doc, KEYS(doc, true))
        """
        return helper.execute_query(
            query.replace('#more_filters', '\n'.join(filters)).replace(
                '#sort_statement', self.get_sort_stmt(self.SORT_PROPERTIES)
            )
        , bind_vars=bind_vars)

    def get_report_objects(self, report_id):
        helper = ArangoDBHelper(settings.VIEW_NAME, self.request)

        types = helper.query.get('types', "")
        filters = []
        bind_vars = {
                "@collection": settings.VIEW_NAME,
                'report_id': report_id,
                "types": list(OBJECT_TYPES.intersection(types.split(","))) if types else None,
        }
        visible_to_filter = ''
        if q := helper.query.get('visible_to'):
            bind_vars['visible_to'] = q
            bind_vars['marking_visible_to_all'] = TLP_LEVEL_STIX_ID_MAPPING[TLP_Levels.GREEN], TLP_LEVEL_STIX_ID_MAPPING[TLP_Levels.CLEAR]
            visible_to_filter = 'FILTER doc.created_by_ref == @visible_to OR @marking_visible_to_all ANY IN doc.object_marking_refs'
        if q := helper.query_as_bool('ignore_embedded_sro', default=False):
            filters.append('FILTER doc._is_ref != TRUE')

        query = """
            LET report = FIRST(
                FOR doc in @@collection
                SEARCH doc.id == @report_id
                #visible_to
                RETURN doc.id
            )
            FOR doc in @@collection
            SEARCH report != NULL AND doc._stixify_report_id == @report_id
            FILTER NOT @types OR doc.type IN @types
            #more_filters
            LIMIT @offset, @count
            RETURN KEEP(doc, KEYS(doc, TRUE))
        """.replace('#visible_to', visible_to_filter).replace('#more_filters', '\n'.join(filters))
        return helper.execute_query(query, bind_vars=bind_vars)

@extend_schema_view(
    destroy=extend_schema(
        summary="Delete all objects associated with identity",
        description=textwrap.dedent(
            """
            This endpoint will delete all Files, Reports, and any other STIX objects created using this identity.
            """
        ),
    ),
    list=extend_schema(
        summary="Search identity objects",
        description=textwrap.dedent(
            """
            This endpoint will allow you to search for all identities that exist.
            """
        ),
    ),
    retrieve=extend_schema(
        summary="GET identity object by STIX ID",
        description=textwrap.dedent(
            """
            This endpoint will allow you to GET an identity object by its STIX ID.
            """
        ),
    ),
)
class IdentityView(viewsets.ViewSet):
    
    SORT_PROPERTIES = [
        "created_descending",
        "created_ascending",
        "name_descending",
        "name_ascending",
    ]
    SYSTEM_IDENTITIES = [
        "identity--72e906ce-ca1b-5d73-adcd-9ea9eb66a1b4",
        "identity--9779a2db-f98c-5f4b-8d08-8ee04e02dbb5",
        "identity--f92e15d9-6afc-5ae2-bb3e-85a1fd83a3b5"
    ]
    openapi_tags = ["Identities"]
    skip_list_view = True
    lookup_url_kwarg = "identity_id"
    lookup_value_regex = r'identity--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    openapi_path_params = [
        OpenApiParameter(
            lookup_url_kwarg, location=OpenApiParameter.PATH, type=dict(pattern=lookup_value_regex),
            description="The full STIX `id` of the Identity object. e.g. `identity--cfc24d7a-0b5e-4068-8bfc-10b66059afe0`."
        )
    ]
    def destroy(self, request, *args, identity_id=None, **kwargs):
        helper = ArangoDBHelper(settings.VIEW_NAME, self.request)
        vertices = helper.execute_query('''
            FOR doc IN stixify_vertex_collection
            FILTER doc.id == @identity_id OR doc.created_by_ref == @identity_id
            RETURN KEEP(doc, "_key", "_id")
        ''', bind_vars=dict(identity_id=identity_id), paginate=False)
        edges = helper.execute_query('''
            FOR doc IN stixify_edge_collection
            FILTER 
                    doc.id == @identity_id OR
                    doc.created_by_ref == @identity_id OR
                    doc._from IN @vertex_ids OR doc._to IN @vertex_ids
            RETURN KEEP(doc, "_key", "_id")
        ''',
            bind_vars=dict(
                identity_id=identity_id,
                vertex_ids=[v['_id'] for v in vertices]),
            paginate=False
        )
        logging.info(f'removing {len(edges)} edges and {len(vertices)} vertices')
        for collection, documents in [('stixify_vertex_collection', vertices), ('stixify_edge_collection', edges)]:
            helper.db.collection(collection).delete_many(documents, silent=True)
        File.objects.filter(identity__id=identity_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @extend_schema(
        responses=ArangoDBHelper.get_paginated_response_schema(),
        parameters=ArangoDBHelper.get_schema_operation_parameters() + [
            OpenApiParameter('name', description="Filter by the `name` of identity object. Search is wildcard so `co` will match `company`, `cointel`, etc."),
            OpenApiParameter('sort', description="Sort the results by selected property", enum=SORT_PROPERTIES),
        ],
    )
    def list(self, request, *args, **kwargs):
        helper = ArangoDBHelper(settings.VIEW_NAME, self.request)
        binds = {
            "@view": settings.VIEW_NAME,
            "system_identities": self.SYSTEM_IDENTITIES,
        }
        more_filters = []
        if name := helper.query.get('name'):
            binds['name'] = "%" + name.replace('%', r'\%') + "%"
            more_filters.append('FILTER doc.name LIKE @name')

        more_filters.append("FILTER doc.id NOT IN @system_identities")

        query = """
        FOR doc IN @@view
        SEARCH doc.type == "identity" AND doc._is_latest == TRUE
        #more_filters
        #sort_stmt
        LIMIT @offset, @count
        RETURN KEEP(doc, KEYS(doc, TRUE))
        """
    
        query = query.replace(
            '#sort_stmt', helper.get_sort_stmt(
                self.SORT_PROPERTIES
            )
        ).replace('#more_filters', '\n'.join(more_filters))
        return helper.execute_query(query, bind_vars=binds)
    
    def retrieve(self, request, *args, identity_id=None, **kwargs):
        helper = ArangoDBHelper(settings.VIEW_NAME, self.request)
        binds = {
            "@view": settings.VIEW_NAME,
            "identity_id": identity_id,
        }
        query = """
        FOR doc IN @@view
        SEARCH doc.type == "identity" AND doc._is_latest == TRUE AND doc.id == @identity_id
        COLLECT id = doc.id INTO docs LET doc = docs[0].doc
        LIMIT @offset, @count
        RETURN KEEP(doc, KEYS(doc, TRUE))
        """
        return helper.execute_query(query, bind_vars=binds)
