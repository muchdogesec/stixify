from stixify.web import models


def test_upload_to_func(db, stixify_file):
    image = models.FileImage.objects.create(report=stixify_file)
    assert models.upload_to_func(stixify_file, "ade.pdf") == "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30/report--dcbeb240-8dd6-4892-8e9e-7b6bda30e454/dcbeb240-8dd6-4892-8e9e-7b6bda30e454_ade.pdf"
    assert models.upload_to_func(image, "ade.png") == "identity--c5f27ca2-a580-4fee-9bb9-753e2b563a30/report--dcbeb240-8dd6-4892-8e9e-7b6bda30e454/dcbeb240-8dd6-4892-8e9e-7b6bda30e454_ade.png"