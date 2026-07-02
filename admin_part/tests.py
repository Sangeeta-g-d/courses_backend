from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from admin_part.utils import compress_image


class CompressImageTests(TestCase):
    def test_compress_image_uses_clean_filename(self):
        image = Image.new('RGB', (100, 100), color='red')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')

        uploaded_file = SimpleUploadedFile(
            'bundle_thumbnails/001.jpg',
            buffer.getvalue(),
            content_type='image/jpeg',
        )

        compressed_file = compress_image(uploaded_file)

        self.assertEqual(compressed_file.name, '001.jpg')
        self.assertNotIn('bundle_thumbnails/', compressed_file.name)
