"""Defines a class for building dynamic protobuf messages.
"""
import uuid
import os

from google.protobuf.descriptor_pb2 import FileDescriptorProto
from google.protobuf.descriptor_pb2 import DescriptorProto
from google.protobuf.message_factory import MessageFactory

from bonsai.proto import inkling_types_pb2

# The message factory
_message_factory = MessageFactory()

# (Relying on Python module implementation being thread-safe here...)
# Add our custom inkling types into the message factory pool so
# they are available to the message factory.
_inkling_file_descriptor = FileDescriptorProto()
inkling_types_pb2.DESCRIPTOR.CopyToProto(_inkling_file_descriptor)
_message_factory.pool.Add(_inkling_file_descriptor)


def _create_package_from_fields(descriptor_proto):
    """
    This generates a "package" name from the fields in a descriptor proto.
    :param descriptor_proto: The DescriptorProto object to analyze.
    :return: Unique "hash" of the fields and field types in descriptor_proto.
    """
    elements = (tuple((f.name, f.number, f.label, f.type, f.type_name)
                      for f in descriptor_proto.field)
                if descriptor_proto else ())

    # The hash function here is used only to generate an identifier that's
    # always the same given the same set of "elements"; since it isn't going
    # to be persisted and reused anywhere and will only be used in this Python
    # process, it's okay if the underlying implementation itself changes from
    # Python version to Python version.
    signature = hash(elements)

    # Sometimes, the built-in hash function used above returns a negative
    # number; this replaces that sign with a identifier-friendly underscore.
    return 'p{}'.format(signature).replace('-', '_')


def _make_descriptor(descriptor_proto, package, full_name):
    """
    We basically need to re-implement the CPP API implementation of Protobuf's
    MakeDescriptor call here. The one provided by Google creates a file
    descriptor proto with a GUID-ish name, sticks the provided descriptor
    proto, adds that file into a default descriptor pool, then calls on the
    descriptor pool to return a descriptor with everything resolved.
    Unfortunately, if you have fields that are message types which require
    importing another file, there's no way to provide that import in the
    default MakeDescriptor() call.

    This call basically copies the default implementation, but instead of using
    the default pool, it uses a custom descriptor pool with Bonsai's Inkling
    Types already imported. It also adds the required import to the generated
    FileDescriptorProto for the schema represented by descriptor_proto.

    for reference, see:
    https://github.com/google/protobuf/python/google/protobuf/descriptor.py

    :param descriptor_proto: The descriptor proto to turn into a descriptor.
    :return: A descriptor corresponding to descriptor_proto.
    """

    # The descriptor may already exist... look for it first.
    pool = _message_factory.pool
    try:
        return pool.FindMessageTypeByName(full_name)
    except KeyError:
        pass

    proto_name = str(uuid.uuid4())
    proto_path = os.path.join(package, proto_name + '.proto')
    file_descriptor_proto = FileDescriptorProto()
    file_descriptor_proto.message_type.add().MergeFrom(descriptor_proto)
    file_descriptor_proto.name = proto_path
    file_descriptor_proto.package = package
    file_descriptor_proto.dependency.append('bonsai/proto/inkling_types.proto')

    # Not sure why this is needed; there's no documentation indicating how this
    # field is used. Some Google unit tests do this when adding a dependency,
    # so it's being done here too.
    file_descriptor_proto.public_dependency.append(0)

    pool.Add(file_descriptor_proto)
    result = pool.FindFileByName(proto_path)
    return result.message_types_by_name[descriptor_proto.name]


def reconstitute(descriptor_proto):
    """
    Reconstitutes a Python protobuf class from a DescriptorProto
    message. Use this instead of reconstitute_from_bytes if you've
    already got a DescriptorProto message.
    """

    if not descriptor_proto.name:
        # This is an anonymous schema
        descriptor_proto.name = '__INTERNAL_ANONYMOUS__'

    # We may have already reconstituted a class for this descriptor. If so,
    # use it.
    package = _create_package_from_fields(descriptor_proto)
    full_name = '{}.{}'.format(package, descriptor_proto.name)

    # Must be brand new. Rebuild it.
    descriptor = _make_descriptor(descriptor_proto, package, full_name)
    cls = _message_factory.GetPrototype(descriptor)
    return cls


def reconstitute_from_bytes(descriptor_proto_bytes):
    """
    Reconstitutes a Python protobuf class from the serialized form of
    a descriptor proto.
    """
    descriptor_proto = DescriptorProto()
    descriptor_proto.ParseFromString(descriptor_proto_bytes)
    return reconstitute(descriptor_proto)
