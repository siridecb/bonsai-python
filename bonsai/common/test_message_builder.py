import unittest

from google.protobuf.descriptor_pb2 import FileDescriptorProto
from google.protobuf.descriptor_pb2 import FieldDescriptorProto

from bonsai.common.message_builder import reconstitute_from_bytes


class MessageReconstitute(unittest.TestCase):

    def test_reconstitute_single_schema(self):
        fdp = FileDescriptorProto()
        fdp.name = 'test_schemas'
        mt = fdp.message_type.add()
        mt.name = 'tests'
        f1 = mt.field.add()
        f1.name = 'a'
        f1.number = 1
        f1.type = FieldDescriptorProto.TYPE_UINT32
        f1.label = FieldDescriptorProto.LABEL_OPTIONAL
        bytes = mt.SerializeToString()
        Test = reconstitute_from_bytes(bytes)
        test = Test()
        test.a = 42
        self.assertEqual(42, test.a)

    def test_reconstitute_composite_schema_with_luminance(self):
        fdp = FileDescriptorProto()
        fdp.name = 'test_schemas'
        mt = fdp.message_type.add()
        mt.name = 'tests'
        f1 = mt.field.add()
        f1.name = 'a'
        f1.number = 1
        f1.type = FieldDescriptorProto.TYPE_MESSAGE
        f1.label = FieldDescriptorProto.LABEL_OPTIONAL
        f1.type_name = 'bonsai.inkling_types.proto.Luminance'
        bytes = mt.SerializeToString()
        Test = reconstitute_from_bytes(bytes)
        test = Test()
        test.a.width = 42
        self.assertEqual(42, test.a.width)


# PyCharm uses the below lines to allow running unit tests with its own
# unit testing engine. The lines below are added by the PyCharm Python
# unit tests template.
if __name__ == '__main__':
    unittest.main()
