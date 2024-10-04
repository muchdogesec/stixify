from django.shortcuts import redirect
from rest_framework import viewsets, parsers, mixins, decorators, status

from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .models import File, Dossier, Job
from .serializers import FileCreateSerializer, FileSerializer, DossierSerializer, JobSerializer
from .utils import Pagination, Ordering, Response
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, Filter, BaseCSVFilter, ChoiceFilter
import django_filters.rest_framework as filters
from stixify.worker.tasks import new_task
from drf_spectacular.utils import extend_schema, extend_schema_view
# Create your views here.
@extend_schema_view(
    list=extend_schema(
        summary="Search and retrieve a list of uploaded Files",
        description="This endpoint allows you to search for Files you've uploaded. This endpoint is paticularly useful if you want to download the original File uploaded or find the Report object created for the uploaded File so you can retrieve the objects created for it.",
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
        description="This endpoint will return `.markdown` content created for the processed file that is used to make the extractions from. This endpoint is useful for debugging issues in extractions when you think there could be an issue with the content being passed to the extractors.",
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

@extend_schema_view(
    list=extend_schema(
        summary="Search and retrieve a list of created Dossiers",
        description="This endpoint will return a list of all Dossiers created and information about them.",
    ),
    create=extend_schema(
        summary="Create a New Dossier",
        description="This endpoint allows you create a Dossier you can use to group Reports together.\n\n *`name`: up to 128 characters\n\n*`description`: up to 512 characters",
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