import unittest
from pprint import pprint

from google.protobuf.descriptor_pb2 import FileDescriptorProto
from google.protobuf.descriptor_pb2 import FieldDescriptorProto

from bonsai.common.message_builder import reconstitute_from_bytes


def _serialize_type_from_description(name, fields):
    fdp = FileDescriptorProto()
    fdp.name = '{}.proto'.format(name)
    mt = fdp.message_type.add()
    mt.name = name

    for idx, field in enumerate(fields):
        f = mt.field.add()
        f.name = field[0]
        f.number = idx + 1
        f.type = field[1]
        f.label = FieldDescriptorProto.LABEL_OPTIONAL
        if f.type == FieldDescriptorProto.TYPE_MESSAGE:
            f.type_name = field[2]

    data = mt.SerializeToString()
    return data


class MessageReconstitute(unittest.TestCase):

    def test_reconstitute_single_schema(self):
        """
        Tests the reconstitution of a schema with 1 primitive field
        """
        data = _serialize_type_from_description(
            'test_single_schema', [('a', FieldDescriptorProto.TYPE_UINT32)]
        )
        test_class = reconstitute_from_bytes(data)
        test = test_class()
        test.a = 42
        self.assertEqual(42, test.a)

    def test_reconstitute_composite_schema_with_luminance(self):
        """
        Tests the reconstitution of a schema with 1 structure field
        """
        data = _serialize_type_from_description(
            'test_composite_schema', [('a',
                                       FieldDescriptorProto.TYPE_MESSAGE,
                                       'bonsai.inkling_types.proto.Luminance')]
        )
        test_class = reconstitute_from_bytes(data)
        test = test_class()
        test.a.width = 42
        self.assertEqual(42, test.a.width)

    def test_reconstitute_two_schemas_same_name_different_fields(self):
        """
        Tests that reconstituting two schemas with the same name but
        different fields result in two classes.
        """
        data1 = _serialize_type_from_description(
            'same_name_1', [('a', FieldDescriptorProto.TYPE_UINT32)]
        )
        data2 = _serialize_type_from_description(
            'same_name_1', [('a', FieldDescriptorProto.TYPE_STRING)]
        )
        self.assertNotEqual(data1, data2)
        test_class_1 = reconstitute_from_bytes(data1)
        test_class_2 = reconstitute_from_bytes(data2)
        self.assertNotEqual(test_class_1, test_class_2)

    def test_reconstitute_two_schemas_same_name_same_fields(self):
        """
        Tests that reconsitituting two schemas with the same name and same
        fields results in the same class.
        """
        data = _serialize_type_from_description(
            'same_name_2', [('a', FieldDescriptorProto.TYPE_UINT32)]
        )
        test_class_1 = reconstitute_from_bytes(data)
        test_class_2 = reconstitute_from_bytes(data)
        self.assertEqual(test_class_1, test_class_2)

    def test_reconstitute_two_schemas_different_names_same_fields(self):
        """
        Tests that reconstituting two schemas with different names and the same
        fields results in different classes.
        """
        data1 = _serialize_type_from_description(
            'test_5_1', [('a', FieldDescriptorProto.TYPE_UINT32)]
        )
        data2 = _serialize_type_from_description(
            'test_5_2', [('a', FieldDescriptorProto.TYPE_UINT32)]
        )
        self.assertNotEqual(data1, data2)
        test_class_1 = reconstitute_from_bytes(data1)
        test_class_2 = reconstitute_from_bytes(data2)
        self.assertNotEqual(test_class_1, test_class_2)

    def test_reconstitute_two_schemas_different_names_different_fields(self):
        """
        Tests that reconstituting two schemas with different names and
        different fields results in different classes.
        """
        data1 = _serialize_type_from_description(
            'test_6_1', [('a', FieldDescriptorProto.TYPE_UINT32)]
        )
        data2 = _serialize_type_from_description(
            'test_6_2', [('a', FieldDescriptorProto.TYPE_STRING)]
        )
        self.assertNotEqual(data1, data2)
        test_class_1 = reconstitute_from_bytes(data1)
        test_class_2 = reconstitute_from_bytes(data2)
        self.assertNotEqual(test_class_1, test_class_2)


# PyCharm uses the below lines to allow running unit tests with its own
# unit testing engine. The lines below are added by the PyCharm Python
# unit tests template.
if __name__ == '__main__':
    unittest.main()
