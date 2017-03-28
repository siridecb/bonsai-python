"""Defines a class for building dynamic protobuf messages.
"""
from google.protobuf.descriptor_pb2 import FileDescriptorProto
from google.protobuf.descriptor_pb2 import DescriptorProto
from google.protobuf.descriptor_pb2 import FieldDescriptorProto
from google.protobuf.descriptor import MakeDescriptor, FieldDescriptor
from google.protobuf.message_factory import MessageFactory

from bonsai.proto import inkling_types_pb2

PACKAGE = "bonsai.proto"
descriptor_cache = {}


def reconstitute(descriptor_proto):
    """
    Reconstitutes a Python protobuf class from a DescriptorProto
    message. Use this instead of reconstitute_from_bytes if you've
    already got a DescriptorProto message.

    Note that the DescriptorPool in MessageFactory doesn't resolve message
    types for composite schemas (i.e. a Luminance or Matrix schema
    type field in the message). So, we add fields in the descriptor marked
    as a TYPE_MESSAGE into 'fields_to_resolve' and after the Descriptor
    is created, we go back and associates the appropriate structure
    with those fields.
    """
    global _descriptor_cache
    proto_bytes = descriptor_proto.SerializeToString()

    if proto_bytes not in descriptor_cache:
        prototype = _reconstitute_proto(descriptor_proto)
        descriptor_cache[proto_bytes] = prototype
    return descriptor_cache[proto_bytes]


def _reconstitute_proto(descriptor_proto):
    # Add our custom inkling types into the message factory pool so
    # they are available to the message factory.
    inkling_file_descriptor = FileDescriptorProto()
    inkling_types_pb2.DESCRIPTOR.CopyToProto(inkling_file_descriptor)
    message_factory = MessageFactory()
    message_factory.pool.Add(inkling_file_descriptor)

    fields_to_resolve = {}
    for field in descriptor_proto.field:
        if field.type == FieldDescriptorProto.TYPE_MESSAGE:
            fields_to_resolve[field.name] = field.type_name

    descriptor = MakeDescriptor(descriptor_proto, PACKAGE)

    for field in descriptor.fields:
        if field.type == FieldDescriptor.TYPE_MESSAGE:
            type_name = fields_to_resolve[field.name]
            message_type = message_factory.pool.FindMessageTypeByName(
                type_name)
            field.message_type = message_type

    return message_factory.GetPrototype(descriptor)


def reconstitute_from_bytes(descriptor_proto_bytes):
    """
    Reconstitutes a Python protobuf class from the serialized form of
    a descriptor proto.
    """
    descriptor_proto = DescriptorProto()
    descriptor_proto.ParseFromString(descriptor_proto_bytes)
    return reconstitute(descriptor_proto)
