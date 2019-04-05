"""
    ESSArch is an open source archiving and digital preservation system

    ESSArch Tools for Producer (ETP)
    Copyright (C) 2005-2017 ES Solutions AB

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <http://www.gnu.org/licenses/>.

    Contact information:
    Web - http://www.essolutions.se
    Email - essarch@essolutions.se
"""
import tempfile
from unittest import mock

import filecmp
import glob
import os
import shutil

from django.contrib.auth.models import User, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from rest_framework import status, exceptions
from rest_framework.response import Response
from rest_framework.test import APIClient, force_authenticate

from ESSArch_Core.auth.models import Group, GroupMember, GroupMemberRole, GroupType
from ESSArch_Core.configuration.models import EventType, Path
from ESSArch_Core.ip.models import InformationPackage
from ESSArch_Core.profiles.models import Profile, ProfileIP, SubmissionAgreement
from ESSArch_Core.WorkflowEngine.models import ProcessTask
from rest_framework_extensions.test import APIRequestFactory

from ESSArch_TP.ip.views import InformationPackageViewSet


class CreateIPTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('informationpackage-list')

        self.user = User.objects.create(username='user')
        self.member = self.user.essauth_member

        self.client.force_authenticate(user=self.user)

        self.root = os.path.dirname(os.path.realpath(__file__))
        self.datadir = os.path.join(self.root, 'datadir')
        Path.objects.create(entity='path_preingest_prepare', value=self.datadir)

        EventType.objects.create(eventType=10100)
        EventType.objects.create(eventType=10200)

        self.addCleanup(shutil.rmtree, self.datadir)

        try:
            os.mkdir(self.datadir)
        except OSError as e:
            if e.errno != 17:
                raise

    def get_add_permission(self):
        return Permission.objects.get(codename='add_informationpackage')

    def add_to_organization(self):
        self.org_group_type = GroupType.objects.create(label='organization')
        self.org = Group.objects.create(name='organization', group_type=self.org_group_type)

        self.user_role = GroupMemberRole.objects.create(codename='user_role')

        membership = GroupMember.objects.create(member=self.member, group=self.org)
        membership.roles.add(self.user_role)

    def test_without_permission(self):
        data = {'label': 'my label', 'object_identifier_value': 'my objid'}

        res = self.client.post(self.url, data)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(InformationPackage.objects.exists())

    def test_without_organization(self):
        perm = self.get_add_permission()
        self.user.user_permissions.add(perm)

        data = {'label': 'my label', 'object_identifier_value': 'my objid'}
        res = self.client.post(self.url, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(InformationPackage.objects.exists())

    def test_create_ip(self):
        self.add_to_organization()
        perm = self.get_add_permission()
        self.user_role.permissions.add(perm)

        data = {'label': 'my label', 'object_identifier_value': 'my objid'}
        res = self.client.post(self.url, data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            InformationPackage.objects.filter(
                responsible=self.user,
                label=data['label'],
                object_identifier_value=data['object_identifier_value'],
            ).exists()
        )

    def test_create_ip_without_objid(self):
        self.add_to_organization()
        perm = self.get_add_permission()
        self.user_role.permissions.add(perm)

        data = {'label': 'my label'}

        res = self.client.post(self.url, data)
        ip = InformationPackage.objects.get()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(ip.pk), ip.object_identifier_value)

    def test_create_ip_without_label(self):
        self.add_to_organization()
        perm = self.get_add_permission()
        self.user_role.permissions.add(perm)

        data = {'object_identifier_value': 'my objid'}
        res = self.client.post(self.url, data)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(InformationPackage.objects.exists())

    def test_create_ip_with_same_objid_as_existing(self):
        self.add_to_organization()
        perm = self.get_add_permission()
        self.user_role.permissions.add(perm)

        existing = InformationPackage.objects.create(object_identifier_value='objid')

        data = {'label': 'my label', 'object_identifier_value': 'objid'}
        res = self.client.post(self.url, data)

        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(InformationPackage.objects.count(), 1)
        self.assertEqual(InformationPackage.objects.first().pk, existing.pk)

    def test_create_ip_with_same_objid_as_existing_on_disk_but_not_db(self):
        self.add_to_organization()
        perm = self.get_add_permission()
        self.user_role.permissions.add(perm)

        os.mkdir(os.path.join(self.datadir, 'objid'))
        data = {'label': 'my label', 'object_identifier_value': 'objid'}
        res = self.client.post(self.url, data)

        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(InformationPackage.objects.exists())

    def test_create_ip_with_same_label_as_existing(self):
        self.add_to_organization()
        perm = self.get_add_permission()
        self.user_role.permissions.add(perm)

        InformationPackage.objects.create(label='label')
        data = {'label': 'label'}
        res = self.client.post(self.url, data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(InformationPackage.objects.filter(label='label').count(), 2)


class test_delete_ip(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="admin")

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.root = os.path.dirname(os.path.realpath(__file__))
        self.datadir = os.path.join(self.root, 'datadir')

        self.ip = InformationPackage.objects.create(object_path=self.datadir)
        self.url = reverse('informationpackage-detail', args=(str(self.ip.pk),))

        try:
            os.mkdir(self.datadir)
        except OSError as e:
            if e.errno != 17:
                raise

    def tearDown(self):
        try:
            shutil.rmtree(self.datadir)
        except BaseException:
            pass

    def test_delete_ip_without_permission(self):
        res = self.client.delete(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(os.path.exists(self.datadir))

    def test_delete_ip_with_permission(self):
        InformationPackage.objects.filter(pk=self.ip.pk).update(
            responsible=self.user
        )

        res = self.client.delete(self.url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(os.path.exists(self.datadir))


class test_submit_ip(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="admin")

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.root = os.path.dirname(os.path.realpath(__file__))
        self.datadir = os.path.join(self.root, 'datadir')

        Path.objects.create(entity='path_preingest_prepare', value=self.datadir)
        Path.objects.create(entity='path_preingest_reception', value=self.datadir)

        self.ip = InformationPackage.objects.create()
        self.url = reverse('informationpackage-detail', args=(self.ip.pk,))
        self.url = self.url + 'submit/'

        try:
            os.mkdir(self.datadir)
        except OSError as e:
            if e.errno != 17:
                raise

    def tearDown(self):
        try:
            shutil.rmtree(self.datadir)
        except BaseException:
            pass

    def test_not_responsible(self):
        res = self.client.post(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_not_created(self):
        self.ip.responsible = self.user
        self.ip.save()
        res = self.client.post(self.url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_submit_description_profile(self):
        self.ip.responsible = self.user
        self.ip.state = 'Created'
        self.ip.save()
        res = self.client.post(self.url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('ip.views.creation_date', return_value=0)
    @mock.patch('ip.views.ProcessStep.run')
    def test_no_mail(self, mock_step, mock_time):
        self.ip.responsible = self.user
        self.ip.state = 'Created'
        self.ip.save()

        sd = Profile.objects.create(profile_type='submit_description')
        ProfileIP.objects.create(ip=self.ip, profile=sd)

        res = self.client.post(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertFalse(ProcessTask.objects.filter(name="ESSArch_Core.tasks.SendEmail").exists())
        mock_step.assert_called_once()

    def test_with_mail_without_subject(self):
        self.ip.responsible = self.user
        self.ip.state = 'Created'
        self.ip.save()

        tp = Profile.objects.create(
            profile_type='transfer_project',
            specification_data={'preservation_organization_receiver_email': 'foo'}
        )
        ProfileIP.objects.create(ip=self.ip, profile=tp)

        res = self.client.post(self.url, {'body': 'foo'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_with_mail_without_body(self):
        self.ip.responsible = self.user
        self.ip.state = 'Created'
        self.ip.save()

        tp = Profile.objects.create(
            profile_type='transfer_project',
            specification_data={'preservation_organization_receiver_email': 'foo'}
        )
        ProfileIP.objects.create(ip=self.ip, profile=tp)

        res = self.client.post(self.url, {'subject': 'foo'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('ip.views.creation_date', return_value=0)
    @mock.patch('ip.views.ProcessStep.run')
    def test_with_mail(self, mock_step, mock_time):
        self.ip.responsible = self.user
        self.ip.state = 'Created'
        self.ip.save()

        tp = Profile.objects.create(
            profile_type='transfer_project',
            specification_data={'preservation_organization_receiver_email': 'foo'}
        )
        ProfileIP.objects.create(ip=self.ip, profile=tp)

        sd = Profile.objects.create(profile_type='submit_description')
        ProfileIP.objects.create(ip=self.ip, profile=sd)

        res = self.client.post(self.url, {'subject': 'foo', 'body': 'bar'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertTrue(ProcessTask.objects.filter(name="ESSArch_Core.tasks.SendEmail").exists())
        mock_step.assert_called_once()


class test_set_uploaded(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="admin")

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.ip = InformationPackage.objects.create()
        self.url = reverse('informationpackage-detail', args=(str(self.ip.pk),))

    def test_set_uploaded_without_permission(self):
        res = self.client.post('%sset-uploaded/' % self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        self.ip.refresh_from_db()
        self.assertEqual(self.ip.state, '')

    def test_set_uploaded_with_permission(self):
        InformationPackage.objects.filter(pk=self.ip.pk).update(
            responsible=self.user
        )

        res = self.client.post('%sset-uploaded/' % self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.ip.refresh_from_db()
        self.assertEqual(self.ip.state, 'Uploaded')


class UploadTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('user')
        self.member = self.user.essauth_member
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        EventType.objects.create(eventType=50700)

        self.root = os.path.dirname(os.path.realpath(__file__))
        self.datadir = os.path.join(self.root, 'datadir')
        self.src = os.path.join(self.datadir, 'src')
        self.dst = os.path.join(self.datadir, 'dst')

        self.ip = InformationPackage.objects.create(object_path=self.dst, state='Prepared')
        self.baseurl = reverse('informationpackage-detail', args=(self.ip.pk,))

        self.org_group_type = GroupType.objects.create(label='organization')
        self.group = Group.objects.create(name='organization', group_type=self.org_group_type)
        self.group.add_member(self.member)

        self.addCleanup(shutil.rmtree, self.datadir)

        for path in [self.src, self.dst]:
            try:
                os.makedirs(path)
            except OSError as e:
                if e.errno != 17:
                    raise

    def test_upload_file(self):
        perms = {'group': ['view_informationpackage', 'ip.can_upload']}
        self.member.assign_object(self.group, self.ip, custom_permissions=perms)
        InformationPackage.objects.filter(pk=self.ip.pk).update(responsible=self.user)

        srcfile = os.path.join(self.src, 'foo.txt')
        srcfile_chunk = os.path.join(self.src, 'foo.txt_chunk')
        dstfile = os.path.join(self.dst, 'foo.txt')

        with open(srcfile, 'w') as fp:
            fp.write('bar')

        open(srcfile_chunk, 'a').close()

        fsize = os.path.getsize(srcfile)
        block_size = 1
        i = 0
        total = 0

        with open(srcfile, 'rb') as fp:
            while total < fsize:
                chunk = SimpleUploadedFile(srcfile_chunk, fp.read(block_size), content_type='multipart/form-data')
                data = {
                    'flowChunkNumber': i,
                    'flowRelativePath': os.path.basename(srcfile),
                    'file': chunk,
                }
                res = self.client.post(self.baseurl + 'upload/', data, format='multipart')
                self.assertEqual(res.status_code, status.HTTP_200_OK)
                total += block_size
                i += 1

        data = {'path': dstfile}
        res = self.client.post(self.baseurl + 'merge-uploaded-chunks/', data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        uploaded_chunks = glob.glob('%s_*' % dstfile)

        self.assertTrue(filecmp.cmp(srcfile, dstfile, False))
        self.assertEqual(uploaded_chunks, [])

    def test_upload_without_permission(self):
        perms = {'group': ['view_informationpackage']}
        self.member.assign_object(self.group, self.ip, custom_permissions=perms)

        srcfile = os.path.join(self.src, 'foo.txt')

        with open(srcfile, 'w') as fp:
            fp.write('bar')

        with open(srcfile, 'rb') as fp:
            chunk = SimpleUploadedFile(srcfile, fp.read(), content_type='multipart/form-data')
            data = {
                'flowChunkNumber': 0,
                'flowRelativePath': os.path.basename(srcfile),
                'file': chunk,
            }
            res = self.client.post(self.baseurl + 'upload/', data, format='multipart')
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_upload_file_with_square_brackets_in_name(self):
        perms = {'group': ['view_informationpackage', 'ip.can_upload']}
        self.member.assign_object(self.group, self.ip, custom_permissions=perms)
        InformationPackage.objects.filter(pk=self.ip.pk).update(responsible=self.user)

        srcfile = os.path.join(self.src, 'foo[asd].txt')
        dstfile = os.path.join(self.dst, 'foo[asd].txt')

        with open(srcfile, 'w') as fp:
            fp.write('bar')

        with open(srcfile, 'rb') as fp:
            chunk = SimpleUploadedFile(srcfile, fp.read(), content_type='multipart/form-data')
            data = {
                'flowChunkNumber': 0,
                'flowRelativePath': os.path.basename(srcfile),
                'file': chunk,
            }
            self.client.post(self.baseurl + 'upload/', data, format='multipart')

            data = {'path': dstfile}
            self.client.post(self.baseurl + 'merge-uploaded-chunks/', data)
            self.assertTrue(filecmp.cmp(srcfile, dstfile, False))


class test_change_sa(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="admin")

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.ip = InformationPackage.objects.create(responsible=self.user)
        self.url = reverse('informationpackage-detail', args=(str(self.ip.pk),))

        self.sa = SubmissionAgreement.objects.create()
        self.sa_url = reverse('submissionagreement-detail', args=(str(self.sa.pk),))

    def test_no_sa(self):
        res = self.client.patch(self.url, {'submission_agreement': self.sa_url}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.ip.refresh_from_db()
        self.assertEqual(self.ip.submission_agreement, self.sa)

    def test_unlocked_sa(self):
        self.ip.submission_agreement = SubmissionAgreement.objects.create()
        self.ip.save()

        res = self.client.patch(self.url, {'submission_agreement': self.sa_url}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.ip.refresh_from_db()
        self.assertEqual(self.ip.submission_agreement, self.sa)

    def test_locked_sa(self):
        self.ip.submission_agreement = SubmissionAgreement.objects.create()
        self.ip.submission_agreement_locked = True
        self.ip.save()

        res = self.client.patch(self.url, {'submission_agreement': self.sa_url}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.ip.refresh_from_db()
        self.assertNotEqual(self.ip.submission_agreement, self.sa)

    def test_not_responsible_for_ip(self):
        self.ip.responsible = User.objects.create(username="stranger")
        self.ip.submission_agreement = SubmissionAgreement.objects.create()
        self.ip.save()

        res = self.client.patch(self.url, {'submission_agreement': self.sa_url}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        self.ip.refresh_from_db()
        self.assertNotEqual(self.ip.submission_agreement, self.sa)


class test_change_profile(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="admin")

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.ip = InformationPackage.objects.create(responsible=self.user)
        self.url = reverse('informationpackage-detail', args=(str(self.ip.pk),))
        self.url = '%schange-profile/' % self.url

        self.profile_type = 'foo'
        self.profile = Profile.objects.create(profile_type=self.profile_type)

    def test_no_profile(self):
        res = self.client.put(self.url, {'new_profile': str(self.profile.pk)}, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(ProfileIP.objects.filter(profile=self.profile, ip=self.ip).exists())

    def test_unlocked_profile(self):
        ProfileIP.objects.create(profile=Profile.objects.create(profile_type=self.profile_type), ip=self.ip)
        res = self.client.put(self.url, {'new_profile': str(self.profile.pk)}, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(ProfileIP.objects.filter(profile=self.profile, ip=self.ip).exists())

    def test_locked_profile(self):
        ProfileIP.objects.create(
            profile=Profile.objects.create(profile_type=self.profile_type), ip=self.ip, LockedBy=self.user
        )
        res = self.client.put(self.url, {'new_profile': str(self.profile.pk)}, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(ProfileIP.objects.filter(profile=self.profile, ip=self.ip).exists())


class DeletePathTests(TestCase):

    def setUp(self):
        self.datadir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datadir)
        self.view = InformationPackageViewSet()

    def test_when_path_does_not_exist(self):
        none_existing_path = os.path.join(self.datadir, "some_other_dir")
        ip = InformationPackage.objects.create(object_path=none_existing_path)
        data = {'path': 'some_path'}

        with self.assertRaisesRegex(exceptions.NotFound, "Path does not exist"):
            self.view.delete_path(data, ip)

    def test_when_path_parameter_does_not_exist(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)
        data = {}

        resp = self.view.delete_path(data, ip)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data, "Path parameter missing")

    def test_when_passed_path_is_not_subdir_of_object_path(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)
        data = {'path': tempfile.mkdtemp()}

        with self.assertRaisesRegex(exceptions.ParseError, f"Illegal path {data['path']}"):
            self.view.delete_path(data, ip)

    def test_when_passed_path_is_a_dir(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)

        tmp_dir_path = os.path.join(self.datadir, 'some_dir')
        os.makedirs(tmp_dir_path)

        data = {'path': tmp_dir_path}

        # Make sure file exists before deletion
        self.assertTrue(os.path.isdir(tmp_dir_path))
        self.view.delete_path(data, ip)
        self.assertFalse(os.path.exists(tmp_dir_path))

    def test_when_passed_path_is_a_file(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)

        tmp_file_path = os.path.join(self.datadir, 'some_file')
        with open(tmp_file_path, 'a') as tmp_file:
            tmp_file.write("dummy")

        data = {'path': tmp_file_path}

        # Make sure file exists before deletion
        self.assertTrue(os.path.isfile(tmp_file_path))
        self.view.delete_path(data, ip)
        self.assertFalse(os.path.isfile(tmp_file_path))


class CreatePathTests(TestCase):

    def setUp(self):
        self.datadir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datadir)
        self.view = InformationPackageViewSet()

    def test_when_path_parameter_does_not_exist(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)
        data = {}

        resp = self.view.create_path(data, ip)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data, "Path parameter missing")

    def test_when_type_parameter_does_not_exist(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)
        data = {'path': 'dummy'}

        resp = self.view.create_path(data, ip)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data, "Type parameter missing")

    def test_when_passed_path_is_not_subdir_of_object_path(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)
        data = {
            'path': tempfile.mkdtemp(),
            'type': 'dummy'
        }

        with self.assertRaisesRegex(exceptions.ParseError, f"Illegal path {data['path']}"):
            self.view.create_path(data, ip)

    def test_when_path_type_is_not_dir_or_file(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)
        data = {
            'path': tempfile.mkdtemp(dir=self.datadir),
            'type': 'dummy'
        }

        resp = self.view.create_path(data, ip)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data, 'Type must be either "file" or "dir"')

    def test_when_path_type_is_dir_and_already_exists(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)
        data = {
            'path': tempfile.mkdtemp(dir=self.datadir),
            'type': 'dir'
        }

        with self.assertRaisesRegex(exceptions.ParseError, f"Directory {data['path']} already exists"):
            self.view.create_path(data, ip)

    def test_when_path_type_is_dir(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)
        data = {
            'path': os.path.join(self.datadir, 'some_dir_to_create'),
            'type': 'dir'
        }

        resp = self.view.create_path(data, ip)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data, data['path'])

    def test_when_path_type_is_file_and_already_exists(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)

        tmp_file_path = os.path.join(self.datadir, 'some_file')
        with open(tmp_file_path, 'a') as tmp_file:
            tmp_file.write("dummy")

        data = {
            'path': tmp_file_path,
            'type': 'file'
        }

        # Make sure file exists
        self.assertTrue(os.path.isfile(tmp_file_path))
        resp = self.view.create_path(data, ip)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data, data['path'])

    def test_when_path_type_is_file_and_it_doesnt_exist(self):
        ip = InformationPackage.objects.create(object_path=self.datadir)

        tmp_file_path = os.path.join(self.datadir, 'some_file')

        data = {
            'path': tmp_file_path,
            'type': 'file'
        }

        # Make sure file does not exist
        self.assertFalse(os.path.isfile(tmp_file_path))
        resp = self.view.create_path(data, ip)
        self.assertTrue(os.path.isfile(tmp_file_path))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data, data['path'])


class GetPathTests(TestCase):
    factory = APIRequestFactory()

    def setUp(self):
        self.datadir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datadir)
        self.user = User.objects.create()
        self.ip = InformationPackage.objects.create(object_path=self.datadir)
        self.ip.get_path_response = mock.MagicMock(return_value=Response("dummy message", status=status.HTTP_200_OK))
        self.view = InformationPackageViewSet
        self.view.get_object = mock.MagicMock(return_value=self.ip)

    def get_response(self, params, authenticate=True):
        request = self.factory.get('/', params)
        if authenticate:
            force_authenticate(request, user=self.user)

        return self.view.as_view({'get': 'files'})(request, pk=self.ip.pk)

    def test_path_with_no_params(self):
        params = {}
        self.get_response(params)

        self.ip.get_path_response.assert_called_once_with(
            '',
            mock.ANY,
            force_download=False,
            paginator=mock.ANY
        )

    def test_path_download_True(self):
        params = {'download': True}
        self.get_response(params)

        self.ip.get_path_response.assert_called_once_with(
            '',
            mock.ANY,
            force_download='True',
            paginator=mock.ANY
        )

    def test_path_download_False(self):
        params = {'download': False}
        self.get_response(params)

        self.ip.get_path_response.assert_called_once_with(
            '',
            mock.ANY,
            force_download='False',
            paginator=mock.ANY
        )

    def test_path_with_path_set(self):
        params = {'path': 'here_is_some/other_path'}
        self.get_response(params)

        self.ip.get_path_response.assert_called_once_with(
            'here_is_some/other_path',
            mock.ANY,
            force_download=False,
            paginator=mock.ANY
        )

    def test_path_with_path_set_with_extra_trailing_slash(self):
        params = {'path': 'here_is_some/other_path/'}
        self.get_response(params)

        self.ip.get_path_response.assert_called_once_with(
            'here_is_some/other_path',
            mock.ANY,
            force_download=False,
            paginator=mock.ANY
        )


class FilesActionTests(TestCase):
    factory = APIRequestFactory()

    def setUp(self):
        self.datadir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datadir)
        self.ip = InformationPackage.objects.create(object_path=self.datadir)
        self.user = User.objects.create()

        # Mocks
        # We don't want to mock the methods of the real class, since it might/will collide with other test cases
        class MyIPViewSet(InformationPackageViewSet):
            pass
        self.mocked_view = MyIPViewSet
        self.mocked_view.delete_path = mock.MagicMock()
        self.mocked_view.create_path = mock.MagicMock()
        self.mocked_view.get_path = mock.MagicMock()
        self.mocked_view.get_object = mock.MagicMock(return_value=self.ip)

    def get_response(self, method_name, action_name, user, authenticate=True):
        request = getattr(self.factory, method_name)('/')

        if authenticate:
            force_authenticate(request, user=user)

        return self.mocked_view.as_view({method_name: action_name})(request, pk=self.ip.pk)

    def test_get_method(self):
        self.mocked_view.get_path.return_value = Response("some message", status=status.HTTP_200_OK)

        resp = self.get_response('get', 'files', self.user)
        self.assertEqual(resp.data, "some message")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.mocked_view.delete_path.assert_not_called()
        self.mocked_view.create_path.assert_not_called()
        self.mocked_view.get_path.assert_called_once()

    def test_post_method_when_ip_state_is_Prepared(self):
        self.ip.state = 'Prepared'
        self.mocked_view.create_path.return_value = Response("some message", status=status.HTTP_201_CREATED)

        resp = self.get_response('post', 'files', self.user)
        self.assertEqual(resp.data, "some message")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        self.mocked_view.delete_path.assert_not_called()
        self.mocked_view.create_path.assert_called_once()
        self.mocked_view.get_path.assert_not_called()

    def test_post_method_when_ip_state_is_Uploading(self):
        self.ip.state = 'Uploading'
        self.mocked_view.create_path.return_value = Response("some message", status=status.HTTP_201_CREATED)

        resp = self.get_response('post', 'files', self.user)
        self.assertEqual(resp.data, "some message")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        self.mocked_view.delete_path.assert_not_called()
        self.mocked_view.create_path.assert_called_once()
        self.mocked_view.get_path.assert_not_called()

    def test_post_method_when_ip_state_not_Prepared_nor_Uploading(self):
        self.ip.state = 'some other state'
        expected_error_message = "Cannot delete or add content of an IP that is not in 'Prepared' or 'Uploading' state"

        resp = self.get_response('post', 'files', self.user)

        self.assertEqual(resp.data['detail'], expected_error_message)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.mocked_view.delete_path.assert_not_called()
        self.mocked_view.create_path.assert_not_called()
        self.mocked_view.get_path.assert_not_called()

    def test_delete_method_when_ip_state_is_Prepared(self):
        self.ip.state = 'Prepared'
        self.mocked_view.delete_path.return_value = Response("some message", status=status.HTTP_201_CREATED)

        resp = self.get_response('delete', 'files', self.user)
        self.assertEqual(resp.data, "some message")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        self.mocked_view.delete_path.assert_called_once()
        self.mocked_view.create_path.assert_not_called()
        self.mocked_view.get_path.assert_not_called()

    def test_delete_method_when_ip_state_is_Uploading(self):
        self.ip.state = 'Uploading'
        self.mocked_view.delete_path.return_value = Response("some message", status=status.HTTP_201_CREATED)

        resp = self.get_response('delete', 'files', self.user)
        self.assertEqual(resp.data, "some message")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        self.mocked_view.delete_path.assert_called_once()
        self.mocked_view.create_path.assert_not_called()
        self.mocked_view.get_path.assert_not_called()

    def test_delete_method_when_ip_state_not_Prepared_nor_Uploading(self):
        self.ip.state = 'some other state'
        expected_error_message = "Cannot delete or add content of an IP that is not in 'Prepared' or 'Uploading' state"

        resp = self.get_response('delete', 'files', self.user)

        self.assertEqual(resp.data['detail'], expected_error_message)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.mocked_view.delete_path.assert_not_called()
        self.mocked_view.create_path.assert_not_called()
        self.mocked_view.get_path.assert_not_called()
