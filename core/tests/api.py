import json

from django.urls import reverse
import mock
import requests
from rest_framework import status
from rest_framework.test import APITestCase

from taggit.models import Tag

from .helpers import create_image, create_user, create_pin
from core.models import Pin, Image, Board


def _teardown_models():
    Pin.objects.all().delete()
    Image.objects.all().delete()
    Tag.objects.all().delete()
    Board.objects.all().delete()


class _MockResponse(object):
    def __init__(self, url, content, status_code=200, headers=None):
        self.url = url
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def mock_requests_get(url, **kwargs):
    with open('docs/src/imgs/logo-dark.png', 'rb') as f:
        return _MockResponse(url, f.read())


def mock_requests_get_with_non_image_content(url, **kwargs):
    return _MockResponse(url, b"abcd")


def mock_requests_get_404(url, **kwargs):
    return _MockResponse(url, b"<html>not found</html>", status_code=404)


def mock_requests_get_connection_error(url, **kwargs):
    raise requests.exceptions.ConnectionError("boom")


class ImageTests(APITestCase):
    def test_post_create_unsupported(self):
        url = reverse("image-list")
        data = {}
        response = self.client.post(
            url,
            data=data,
            format='json',
        )
        self.assertEqual(response.status_code, 401, response.data)


class BoardPrivacyTests(APITestCase):

    def setUp(self):
        super(BoardPrivacyTests, self).setUp()
        self.owner = create_user("default")
        self.non_owner = create_user("non_owner")

        self.private_board = Board.objects.create(
            name="test_board",
            submitter=self.owner,
            private=True,
        )
        self.board_url = reverse("board-detail", kwargs={"pk": self.private_board.pk})
        self.boards_url = reverse("board-list")

    def tearDown(self):
        _teardown_models()

    def _create_pin_with_non_owner(self, private):
        image = create_image()
        pin = create_pin(self.non_owner, image=image, tags=[])
        pin.private = private
        pin.save()
        return pin

    def test_should_non_owner_and_anonymous_user_has_no_permission_to_list_private_board(self):
        resp = self.client.get(self.boards_url)
        self.assertEqual(len(resp.json()['results']), 0, resp.json())

        self.client.login(username=self.non_owner.username, password='password')
        resp = self.client.get(self.boards_url)
        self.assertEqual(len(resp.json()['results']), 0, resp.content)

    def test_should_owner_has_permission_to_list_private_board(self):
        self.client.login(username=self.owner.username, password='password')
        resp = self.client.get(self.boards_url)
        self.assertEqual(len(resp.json()['results']), 1, resp.content)

    def test_should_non_owner_and_anonymous_user_has_no_permission_to_view_private_board(self):
        resp = self.client.get(self.board_url)
        self.assertEqual(resp.status_code, 404)

        self.client.login(username=self.non_owner.username, password='password')
        resp = self.client.get(self.board_url)
        self.assertEqual(resp.status_code, 404)

    def test_should_owner_has_permission_to_view_private_board(self):
        self.client.login(username=self.owner.username, password='password')
        resp = self.client.get(self.board_url)
        self.assertEqual(resp.status_code, 200)

    def test_should_owner_has_no_permission_to_add_private_pin_of_other_user_to_board(self):
        self.client.login(username=self.owner.username, password='password')

        private_pin_of_other_user = self._create_pin_with_non_owner(True)

        resp = self.client.patch(self.board_url, data={"pins_to_add": [private_pin_of_other_user.id, ]})
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(self.board_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_pins'], 0, resp.json())

    def test_should_owner_has_permission_to_add_non_private_pin_of_other_user_to_board(self):
        self.client.login(username=self.owner.username, password='password')

        private_pin_of_other_user = self._create_pin_with_non_owner(False)

        resp = self.client.patch(self.board_url, data={"pins_to_add": [private_pin_of_other_user.id, ]})
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(self.board_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_pins'], 1, resp.json())


class PinPrivacyTests(APITestCase):

    def setUp(self):
        super(PinPrivacyTests, self).setUp()
        self.owner = create_user("default")
        self.non_owner = create_user("non_owner")

        with mock.patch('requests.get', mock_requests_get):
            image = create_image()
        self.private_pin = Pin.objects.create(
            submitter=self.owner,
            image=image,
            private=True,
        )
        self.private_pin_url = reverse("pin-detail", kwargs={"pk": self.private_pin.pk})

        self.board = Board.objects.create(name="test_board", submitter=self.owner)
        self.board.pins.add(self.private_pin)
        self.board.save()
        self.board_url = reverse("board-detail", kwargs={"pk": self.board.pk})

    def tearDown(self):
        _teardown_models()

    def test_should_non_owner_and_anonymous_user_has_no_permission_to_list_private_pin(self):
        resp = self.client.get(reverse("pin-list"))
        self.assertEqual(len(resp.json()['results']), 0, resp.content)

        self.client.login(username=self.non_owner.username, password='password')
        resp = self.client.get(reverse("pin-list"))
        self.assertEqual(len(resp.json()['results']), 0, resp.content)

    def test_should_owner_user_has_permission_to_list_private_pin(self):
        self.client.login(username=self.owner.username, password='password')
        resp = self.client.get(reverse("pin-list"))
        self.assertEqual(len(resp.json()['results']), 1, resp.content)

    def test_should_owner_has_permission_to_view_private_pin(self):
        self.client.login(username=self.owner.username, password='password')
        resp = self.client.get(self.private_pin_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['id'], self.private_pin.id)

    def test_should_anonymous_user_has_no_permission_to_view_private_pin(self):
        resp = self.client.get(self.private_pin_url)
        self.assertEqual(resp.status_code, 404)

    def test_should_non_owner_has_no_permission_to_view_private_pin(self):
        self.client.login(username=self.non_owner.username, password='password')
        resp = self.client.get(self.private_pin_url)
        self.assertEqual(resp.status_code, 404)


class PinTests(APITestCase):
    _JSON_TYPE = "application/json"

    def setUp(self):
        super(PinTests, self).setUp()
        self.user = create_user("default")
        self.client.login(username=self.user.username, password='password')

    def tearDown(self):
        _teardown_models()

    @mock.patch('requests.get', mock_requests_get_with_non_image_content)
    def test_should_not_create_pin_if_url_content_invalid(self):
        url = 'http://testserver.com/mocked/logo-01.png'
        create_url = reverse("pin-list")
        referer = 'http://testserver.com/'
        post_data = {
            'url': url,
            'private': False,
            'referer': referer,
            'description': 'That\'s an Apple!'
        }
        response = self.client.post(create_url, data=post_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('requests.get', mock_requests_get)
    def test_should_create_pin(self):
        url = 'http://testserver.com/mocked/logo-01.png'
        create_url = reverse("pin-list")
        referer = 'http://testserver.com/'
        post_data = {
            'url': url,
            'private': False,
            'referer': referer,
            'description': 'That\'s an Apple!'
        }
        response = self.client.post(create_url, data=post_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pin = Pin.objects.get(url=url)
        self.assertIsNotNone(pin.image.image)

    @mock.patch('requests.get', mock_requests_get)
    def test_post_create_url_with_empty_tags(self):
        url = 'http://testserver.com/mocked/logo-02.png'
        create_url = reverse("pin-list")
        referer = 'http://testserver.com/'
        post_data = {
            'url': url,
            'referer': referer,
            'description': 'That\'s an Apple!',
            'tags': []
        }
        response = self.client.post(create_url, data=post_data, format="json")
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED, response.json()
        )
        self.assertEqual(Image.objects.count(), 1)
        pin = Pin.objects.get(url=url)
        self.assertIsNotNone(pin.image.image)
        self.assertEqual(pin.tags.count(), 0)

    def test_should_post_create_pin_with_existed_image(self):
        image = create_image()
        create_url = reverse("pin-list")
        referer = 'http://testserver.com/'
        post_data = {
            'referer': referer,
            'image_by_id': image.pk,
            'description': 'That\'s something else (probably a CC logo)!',
            'tags': ['random', 'tags'],
        }
        response = self.client.post(create_url, data=post_data, format="json")
        resp_data = response.json()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, resp_data)
        self.assertEqual(
            resp_data['description'],
            'That\'s something else (probably a CC logo)!',
            resp_data
        )
        self.assertEqual(Pin.objects.count(), 1)

    def test_patch_detail_unauthenticated(self):
        image = create_image()
        pin = create_pin(self.user, image, [])
        self.client.logout()
        uri = reverse("pin-detail", kwargs={"pk": pin.pk})
        response = self.client.patch(uri, format='json', data={})
        self.assertEqual(response.status_code, 401, response.data)

    def test_patch_detail(self):
        image = create_image()
        pin = create_pin(self.user, image, [])
        uri = reverse("pin-detail", kwargs={"pk": pin.pk})
        new = {'description': 'Updated description'}

        response = self.client.patch(
            uri, new, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.json())
        self.assertEqual(Pin.objects.count(), 1)
        self.assertEqual(Pin.objects.get(pk=pin.pk).description, new['description'])

    def test_delete_detail_unauthenticated(self):
        image = create_image()
        pin = create_pin(self.user, image, [])
        uri = reverse("pin-detail", kwargs={"pk": pin.pk})
        self.client.logout()
        resp = self.client.delete(uri)
        self.assertEqual(resp.status_code, 401, resp.data)

    def test_delete_detail(self):
        image = create_image()
        pin = create_pin(self.user, image, [])
        uri = reverse("pin-detail", kwargs={"pk": pin.pk})
        self.client.delete(uri)
        self.assertEqual(Pin.objects.count(), 0)


class SecurityRegressionTests(APITestCase):

    def setUp(self):
        super(SecurityRegressionTests, self).setUp()
        self.owner = create_user("default")
        self.other = create_user("other")

    def tearDown(self):
        _teardown_models()

    def test_pin_and_board_listing_does_not_expose_email(self):
        pin = create_pin(self.owner, create_image(), [])
        board = Board.objects.create(name="b", submitter=self.owner)
        board.pins.add(pin)
        for url in (reverse("pin-list"), reverse("board-list")):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn(self.owner.email, resp.content.decode(), url)
            self.assertNotIn('"email"', resp.content.decode(), url)

    def test_board_cover_does_not_leak_private_pin(self):
        private_pin = create_pin(self.owner, create_image(), [])
        private_pin.private = True
        private_pin.save()
        board = Board.objects.create(name="b", submitter=self.owner)
        board.pins.add(private_pin)
        resp = self.client.get(reverse("board-detail", kwargs={"pk": board.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["cover"])
        self.client.login(username=self.other.username, password='password')
        resp = self.client.get(reverse("board-detail", kwargs={"pk": board.pk}))
        self.assertIsNone(resp.json()["cover"])
        self.client.login(username=self.owner.username, password='password')
        resp = self.client.get(reverse("board-detail", kwargs={"pk": board.pk}))
        self.assertEqual(resp.json()["cover"]["id"], private_pin.id)

    def test_cannot_reuse_image_of_other_users_pin(self):
        image = create_image()
        victim_pin = create_pin(self.owner, image, [])
        self.client.login(username=self.other.username, password='password')
        resp = self.client.post(
            reverse("pin-list"), data={"image_by_id": image.pk}, format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertTrue(Pin.objects.filter(pk=victim_pin.pk).exists())

    def test_image_by_id_with_source_url_does_not_fetch(self):
        image = create_image()
        self.client.login(username=self.owner.username, password='password')
        with mock.patch('requests.get') as get:
            resp = self.client.post(
                reverse("pin-list"),
                data={"image_by_id": image.pk, "url": "https://example.com/page"},
                format="json",
            )
            get.assert_not_called()
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Pin.objects.get().url, "https://example.com/page")

    def _post_url(self, url):
        self.client.login(username=self.owner.username, password='password')
        return self.client.post(reverse("pin-list"), data={"url": url}, format="json")

    @mock.patch('requests.get', mock_requests_get_404)
    def test_remote_404_is_validation_error(self):
        resp = self._post_url("http://example.com/missing.png")
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("url", resp.json())

    @mock.patch('requests.get', mock_requests_get_connection_error)
    def test_remote_connection_error_is_validation_error(self):
        resp = self._post_url("http://example.com/x.png")
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_non_http_scheme_rejected(self):
        with mock.patch('requests.get') as get:
            resp = self._post_url("file:///etc/passwd")
            get.assert_not_called()
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_upload_extension_is_forced_from_image_format(self):
        self.client.login(username=self.owner.username, password='password')
        with open('docs/src/imgs/logo-dark.png', 'rb') as f:
            from django.core.files.uploadedfile import SimpleUploadedFile
            content = f.read()
        html = SimpleUploadedFile("evil.png.html", content, content_type="text/html")
        resp = self.client.post(reverse("image-list"), {"image": html})
        self.assertEqual(resp.status_code, 400, resp.content)
        # a PNG disguised with another image extension is stored as .png
        upload = SimpleUploadedFile("disguised.gif", content, content_type="image/gif")
        resp = self.client.post(reverse("image-list"), {"image": upload})
        self.assertEqual(resp.status_code, 201, resp.content)
        image = Image.objects.get(pk=resp.json()["id"])
        self.assertTrue(image.image.name.endswith(".png"), image.image.name)
        for thumb in image.thumbnail_set.all():
            self.assertTrue(thumb.image.name.endswith(".png"), thumb.image.name)

    def test_upload_non_image_rejected(self):
        self.client.login(username=self.owner.username, password='password')
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile("x.png", b"<script>alert(1)</script>")
        resp = self.client.post(reverse("image-list"), {"image": upload})
        self.assertEqual(resp.status_code, 400, resp.content)
