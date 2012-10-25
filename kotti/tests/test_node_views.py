from webob.multidict import MultiDict
from pyramid.exceptions import Forbidden

from kotti.testing import DummyRequest
from kotti.testing import UnitTestBase


class TestAddableTypes(UnitTestBase):
    def test_view_permitted_yes(self):
        from kotti import DBSession
        from kotti.resources import Node
        from kotti.resources import Document

        self.config.testing_securitypolicy(permissive=True)
        self.config.include('kotti.views.edit')
        root = DBSession.query(Node).get(1)
        request = DummyRequest()
        self.assertEquals(Document.type_info.addable(root, request), True)

    def test_view_permitted_no(self):
        from kotti import DBSession
        from kotti.resources import Node
        from kotti.resources import Document

        self.config.testing_securitypolicy(permissive=False)
        self.config.include('kotti.views.edit')
        root = DBSession.query(Node).get(1)
        request = DummyRequest()
        self.assertEquals(Document.type_info.addable(root, request), False)


class TestNodePaste(UnitTestBase):
    def test_get_non_existing_paste_item(self):
        from kotti import DBSession
        from kotti.resources import Node
        from kotti.views.edit import get_paste_items

        root = DBSession.query(Node).get(1)
        request = DummyRequest()
        request.session['kotti.paste'] = ([1701], 'copy')
        item = get_paste_items(root, request)
        self.assertEqual(item, [])

    def test_paste_non_existing_node(self):
        from kotti import DBSession
        from kotti.resources import Node
        from kotti.views.edit import paste_node

        root = DBSession.query(Node).get(1)
        request = DummyRequest()

        for index, action in enumerate(['copy', 'cut']):
            request.session['kotti.paste'] = ([1701], 'copy')
            response = paste_node(root, request)
            self.assertEqual(response.status, '302 Found')
            self.assertEqual(len(request.session['_f_error']), index + 1)

    def test_paste_without_edit_permission(self):
        from kotti import DBSession
        from kotti.resources import Node
        from kotti.views.edit import paste_node

        root = DBSession.query(Node).get(1)
        request = DummyRequest()
        request.params['paste'] = u'on'
        self.config.testing_securitypolicy(permissive=False)

        # We need to have the 'edit' permission on the original object
        # to be able to cut and paste:
        request.session['kotti.paste'] = ([1], 'cut')
        self.assertRaises(Forbidden, paste_node, root, request)

        # We don't need 'edit' permission if we're just copying:
        request.session['kotti.paste'] = ([1], 'copy')
        response = paste_node(root, request)
        self.assertEqual(response.status, '302 Found')


class TestNodeRename(UnitTestBase):
    def test_rename_to_empty_name(self):
        from kotti import DBSession
        from kotti.resources import Node
        from kotti.resources import Document
        from kotti.views.edit import rename_node

        root = DBSession.query(Node).get(1)
        child = root['child'] = Document(title=u"Child")
        request = DummyRequest()
        request.params['rename'] = u'on'
        request.params['name'] = u''
        request.params['title'] = u'foo'
        rename_node(child, request)
        self.assertEqual(request.session.pop_flash('error'),
                         [u'Name and title are required.'])

    def test_multi_rename(self):
        from kotti import DBSession
        from kotti.resources import Node
        from kotti.resources import Document
        from kotti.views.edit import rename_nodes

        root = DBSession.query(Node).get(1)
        root['child1'] = Document(title=u"Child 1")
        root['child2'] = Document(title=u"Child 2")
        request = DummyRequest()
        request.POST = MultiDict()
        id1 = str(root['child1'].id)
        id2 = str(root['child2'].id)
        request.POST.add('children-to-rename', id1)
        request.POST.add('children-to-rename', id2)
        request.POST.add(id1 + '-name', u'')
        request.POST.add(id1 + '-title', u'Unhappy Child')
        request.POST.add(id2 + '-name', u'happy-child')
        request.POST.add(id2 + '-title', u'')
        request.POST.add('rename_nodes', u'rename_nodes')
        rename_nodes(root, request)
        assert request.session.pop_flash('error') ==\
            [u'Name and title are required.']

        request.POST.add(id1 + '-name', u'unhappy-child')
        request.POST.add(id1 + '-title', u'Unhappy Child')
        request.POST.add(id2 + '-name', u'happy-child')
        request.POST.add(id2 + '-title', u'Happy Child')
        request.POST.add('rename_nodes', u'rename_nodes')
        rename_nodes(root, request)
        assert request.session.pop_flash('success') ==\
            [u'Your changes have been saved.']


class TestNodeDelete(UnitTestBase):

    def test_multi_delete(self):
        from kotti import DBSession
        from kotti.resources import Node
        from kotti.resources import Document
        from kotti.views.edit import delete_nodes

        root = DBSession.query(Node).get(1)
        root['child1'] = Document(title=u"Child 1")
        root['child2'] = Document(title=u"Child 2")

        request = DummyRequest()
        request.POST = MultiDict()
        id1 = str(root['child1'].id)
        id2 = str(root['child2'].id)
        request.POST.add('delete_nodes', u'delete_nodes')
        delete_nodes(root, request)
        assert request.session.pop_flash('info') ==\
            [u'Nothing deleted.']

        request.POST.add('children-to-delete', id1)
        request.POST.add('children-to-delete', id2)
        delete_nodes(root, request)
        assert request.session.pop_flash('success') ==\
            [u'${title} deleted.', u'${title} deleted.']


class TestNodeShare(UnitTestBase):
    @staticmethod
    def add_some_principals():
        from kotti.security import get_principals

        P = get_principals()
        P[u'bob'] = {'name': u'bob', 'title': u"Bob"}
        P[u'frank'] = {'name': u'frank', 'title': u"Frank"}
        P[u'group:bobsgroup'] = {
            'name': u'group:bobsgroup', 'title': u"Bob's Group"}
        P[u'group:franksgroup'] = {
            'name': u'group:franksgroup', 'title': u"Frank's Group"}

    def test_roles(self):
        from kotti.views.users import share_node
        from kotti.resources import get_root
        from kotti.security import SHARING_ROLES

        # The 'share_node' view will return a list of available roles
        # as defined in 'kotti.security.SHARING_ROLES'
        root = get_root()
        request = DummyRequest()
        self.assertEqual(
            [r.name for r in share_node(root, request)['available_roles']],
            SHARING_ROLES)

    def test_search(self):
        from kotti.resources import get_root
        from kotti.security import get_principals
        from kotti.security import set_groups
        from kotti.views.users import share_node

        root = get_root()
        request = DummyRequest()
        P = get_principals()
        self.add_some_principals()

        # Search for "Bob", which will return both the user and the
        # group, both of which have no roles:
        request.params['search'] = u''
        request.params['query'] = u'Bob'
        entries = share_node(root, request)['entries']
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0][0], P['bob'])
        self.assertEqual(entries[0][1], ([], []))
        self.assertEqual(entries[1][0], P['group:bobsgroup'])
        self.assertEqual(entries[1][1], ([], []))

        # We make Bob an Editor in this context, and Bob's Group
        # becomes global Admin:
        set_groups(u'bob', root, [u'role:editor'])
        P[u'group:bobsgroup'].groups = [u'role:admin']
        entries = share_node(root, request)['entries']
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0][0], P['bob'])
        self.assertEqual(entries[0][1], ([u'role:editor'], []))
        self.assertEqual(entries[1][0], P['group:bobsgroup'])
        self.assertEqual(entries[1][1], ([u'role:admin'], [u'role:admin']))

        # A search that doesn't return any items will still include
        # entries with existing local roles:
        request.params['query'] = u'Weeee'
        entries = share_node(root, request)['entries']
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], P[u'bob'])
        self.assertEqual(entries[0][1], ([u'role:editor'], []))
        self.assertEqual(request.session.pop_flash('info'),
                         [u'No users or groups found.'])

        # It does not, however, include entries that have local group
        # assignments only:
        set_groups(u'frank', root, [u'group:franksgroup'])
        request.params['query'] = u'Weeee'
        entries = share_node(root, request)['entries']
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], P['bob'])

    def test_apply(self):
        from kotti.resources import get_root
        from kotti.security import list_groups
        from kotti.security import set_groups
        from kotti.views.users import share_node

        root = get_root()
        request = DummyRequest()
        self.add_some_principals()

        request.params['apply'] = u''
        share_node(root, request)
        self.assertEqual(request.session.pop_flash('info'),
                         [u'No changes made.'])
        self.assertEqual(list_groups('bob', root), [])
        set_groups('bob', root, ['role:special'])

        request.params['role::bob::role:owner'] = u'1'
        request.params['role::bob::role:editor'] = u'1'
        request.params['orig-role::bob::role:owner'] = u''
        request.params['orig-role::bob::role:editor'] = u''

        share_node(root, request)
        self.assertEqual(request.session.pop_flash('success'),
                         [u'Your changes have been saved.'])
        self.assertEqual(
            set(list_groups('bob', root)),
            set(['role:owner', 'role:editor', 'role:special'])
            )

        # We cannot set a role that's not displayed, even if we forged
        # the request:
        request.params['role::bob::role:admin'] = u'1'
        request.params['orig-role::bob::role:admin'] = u''
        self.assertRaises(Forbidden, share_node, root, request)
        self.assertEqual(
            set(list_groups('bob', root)),
            set(['role:owner', 'role:editor', 'role:special'])
            )
