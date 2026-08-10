from stixify.web import models


def test_upload_to_func(db, stixify_file):
    image = models.FileImage.objects.create(report=stixify_file)
    assert models.upload_to_func(stixify_file, "ade.pdf") == "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30/report--dcbeb240-8dd6-4892-8e9e-7b6bda30e454/dcbeb240-8dd6-4892-8e9e-7b6bda30e454_ade.pdf"
    assert models.upload_to_func(image, "ade.png") == "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30/report--dcbeb240-8dd6-4892-8e9e-7b6bda30e454/dcbeb240-8dd6-4892-8e9e-7b6bda30e454_ade.png"


def test_file_added_is_immutable_and_updated_changes(db, stixify_file):
    original_added = stixify_file.added
    original_updated = stixify_file.updated
    stixify_file.name = "Updated name"
    stixify_file.save(update_fields=["name"])
    stixify_file.refresh_from_db()

    assert stixify_file.added == original_added
    assert stixify_file.updated >= original_updated
