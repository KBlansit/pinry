import PIL.Image
import requests

from io import BytesIO
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models
from django.dispatch import receiver

from django_images.models import Image as BaseImage, Thumbnail
from taggit.managers import TaggableManager

from users.models import User


class ImageFetchError(Exception):
    pass


class ImageManager(models.Manager):
    _default_ua = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/48.0.2564.82 Safari/537.36',
    }

    @staticmethod
    def _is_valid_image(fp):
        fp.seek(0)
        try:
            with PIL.Image.open(fp) as im:
                im.verify()
        except Exception:
            fp.seek(0)
            return False
        else:
            fp.seek(0)
            return True

    # Maximum size of a remotely fetched image (matches nginx body limit)
    MAX_REMOTE_IMAGE_SIZE = 50 * 1024 * 1024
    REMOTE_FETCH_TIMEOUT = (10, 30)  # (connect, read) seconds

    def _fetch_remote(self, url, headers):
        """Fetch ``url`` into a BytesIO, raising ImageFetchError on failure."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ImageFetchError("only http(s) image URLs are supported")
        try:
            with requests.get(
                url,
                headers=headers,
                timeout=self.REMOTE_FETCH_TIMEOUT,
                stream=True,
                allow_redirects=True,
            ) as response:
                # don't follow redirects to non-http(s) schemes
                if urlparse(response.url).scheme not in ("http", "https"):
                    raise ImageFetchError("invalid redirect target")
                if response.status_code >= 400:
                    raise ImageFetchError(
                        "remote server responded with HTTP %s" % response.status_code
                    )
                length = response.headers.get("Content-Length")
                if length and length.isdigit() and int(length) > self.MAX_REMOTE_IMAGE_SIZE:
                    raise ImageFetchError("remote image is too large")
                buf = BytesIO()
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    buf.write(chunk)
                    if buf.tell() > self.MAX_REMOTE_IMAGE_SIZE:
                        raise ImageFetchError("remote image is too large")
                return buf
        except requests.exceptions.SSLError:
            raise ImageFetchError(
                "could not verify the remote server's SSL certificate, "
                "please download the image and upload it instead"
            )
        except requests.RequestException as e:
            raise ImageFetchError("failed to fetch image: %s" % e.__class__.__name__)

    # FIXME: Move this into an asynchronous task
    def create_for_url(self, url, referer=None):
        file_name = url.split("/")[-1].split('#')[0].split('?')[0] or "image"
        headers = dict(self._default_ua)
        if referer is not None:
            headers["Referer"] = referer
        buf = self._fetch_remote(url, headers)
        if not self._is_valid_image(buf):
            return None
        buf.seek(0)
        obj = InMemoryUploadedFile(buf, 'image', file_name,
                                   None, buf.getbuffer().nbytes, None)
        # create the image and its thumbnails in one transaction, removing
        # a chance of getting Database into a inconsistent state when we
        # try to create thumbnails one by one later
        image = self.create(image=obj)
        Thumbnail.objects.get_or_create_at_sizes(image, settings.IMAGE_SIZES.keys())
        return image


class Image(BaseImage):
    objects = ImageManager()

    class Sizes:
        standard = "standard"
        thumbnail = "thumbnail"
        square = "square"

    class Meta:
        proxy = True

    @property
    def standard(self):
        return Thumbnail.objects.get(
            original=self, size=self.Sizes.standard
        )

    @property
    def thumbnail(self):
        return Thumbnail.objects.get(
            original=self, size=self.Sizes.thumbnail
        )

    @property
    def square(self):
        return Thumbnail.objects.get(
            original=self, size=self.Sizes.square
        )


class Board(models.Model):
    class Meta:
        # unique_together already creates an index on (submitter, name)
        unique_together = ("submitter", "name")

    submitter = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=128, blank=False, null=False)
    private = models.BooleanField(default=False, blank=False)
    pins = models.ManyToManyField("Pin", related_name="pins", blank=True)

    published = models.DateTimeField(auto_now_add=True)


class Pin(models.Model):
    submitter = models.ForeignKey(User, on_delete=models.CASCADE)
    private = models.BooleanField(default=False, blank=False)
    url = models.CharField(null=True, blank=True, max_length=2048)
    referer = models.CharField(null=True, blank=True, max_length=2048)
    description = models.TextField(blank=True, null=True)
    image = models.ForeignKey(Image, related_name='pin', on_delete=models.CASCADE)
    published = models.DateTimeField(auto_now_add=True)
    tags = TaggableManager()

    def tag_list(self):
        return self.tags.all()

    def __unicode__(self):
        return '%s - %s' % (self.submitter, self.published)


@receiver(models.signals.post_delete, sender=Pin)
def delete_pin_images(sender, instance, **kwargs):
    try:
        instance.image.delete()
    except Image.DoesNotExist:
        pass
