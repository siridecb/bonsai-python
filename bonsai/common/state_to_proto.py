
import logging


log = logging.getLogger(__name__)


class SimStateException(Exception):
    pass


def build_luminance_from_state(field_name, proto_msg, luminance):
    """ This function sets a luminance datum onto a protobuf message """
    if luminance.__class__.__name__ == 'Luminance':
        lum_attr = getattr(proto_msg, field_name)
        lum_attr.width = luminance.width
        lum_attr.height = luminance.height
        lum_attr.pixels = luminance.pixels
    else:
        raise SimStateException(
            'Expected bonsai.inkling_types.Luminance Got {}'
            .format(luminance.__class__))


# inkling_type_tensor_handler maps inkling types by name to handlers built
inkling_type_proto_handler = {
    "bonsai.inkling_types.proto.Luminance": build_luminance_from_state}


def build_proto_from_embedded_type(message_type, field_name, field_data,
                                   proto_msg):
    """ This function builds a protobuf representation for complex inkling
    types. For successful conversion, typenames and handling functions must
    be registered in the mapping inkling_type_proto_handler
    """
    if message_type is not None:
        log.debug("Converting %s type into tensor form",
                  str(message_type.full_name))
        handler = inkling_type_proto_handler[message_type.full_name]
        handler(field_name, proto_msg, field_data)
    else:
        log.error("build_proto_from_embedded_type unable to process"
                  " message with empty message_type")


def is_proto_type_embedded_message(field):
    """ This function tests whether a particular field is a simple type or a
    complex type that needs explicit handling
    """
    return field.type == field.TYPE_MESSAGE


def is_proto_type_float(field):
    """ This function determines if the protobuf-field type should resolve
    to a float
    """
    return field.type == field.TYPE_DOUBLE or field.type == field.TYPE_FLOAT


def is_proto_type_integer(field):
    """ This function determines if the protobuf-field type should resolve
    to an integer
    """
    if (field.type == field.TYPE_INT32 or
            field.type == field.TYPE_INT64 or
            field.type == field.TYPE_SINT32 or
            field.type == field.TYPE_SINT64 or
            field.type == field.TYPE_UINT32 or
            field.type == field.TYPE_UINT64):
        return True
    return False


def is_proto_type_boolean(field):
    """ This function determines if the protobuf-field type should resolve
    to a boolean
    """
    return field.type == field.TYPE_BOOL


def is_proto_type_string(field):
    """ This function determines if the protobuf-field type should resolve
    to a string
    """
    return field.type == field.TYPE_STRING


def convert_state_to_proto(state_msg, state):
    for field in state_msg.DESCRIPTOR.fields:
        try:
            value = state[field.name]
        except KeyError:
            raise SimStateException(
                'The inkling file specifies a field named "{}" which was not '
                'found in the SimState. Please check the inkling file state '
                'schema and the return value from get_state().'
                .format(field.name))
        # If the field is a message, assume it is Luminance.
        if is_proto_type_embedded_message(field):
            build_proto_from_embedded_type(
                field.message_type, field.name, value, state_msg)
        elif is_proto_type_float(field):
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise SimStateException(
                    'Expected the field "{}" to be a float, but got {} '
                    'instead.'.format(field.name, repr(value)))
            setattr(state_msg, field.name, value)
        elif is_proto_type_integer(field):
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise SimStateException(
                    'Expected the field "{}" to be an integer, but got {} '
                    'instead.'.format(field.name, repr(value)))
            setattr(state_msg, field.name, value)
        elif is_proto_type_boolean(field):
            try:
                value = bool(value)
            except (TypeError, ValueError):
                raise SimStateException(
                    'Expected the field "{}" to be a boolean, but got {} '
                    'instead.'.format(field.name, repr(value)))
            setattr(state_msg, field.name, value)
        elif is_proto_type_string(field):
            try:
                value = str(value)
            except (TypeError, ValueError):
                raise SimStateException(
                    'Expected the field "{}" to be a string, but got {} '
                    'instead.'.format(field.name, repr(value)))
            setattr(state_msg, field.name, value)
