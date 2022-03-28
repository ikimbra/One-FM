# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: facial_recognition.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x18\x66\x61\x63ial_recognition.proto\"N\n\x07Request\x12\x10\n\x08username\x18\x01 \x01(\t\x12\x1a\n\x12user_encoded_video\x18\x02 \x01(\t\x12\x15\n\ruser_encoding\x18\x03 \x01(\t\"Q\n\x08Response\x12\x0f\n\x07message\x18\x01 \x01(\t\x12\x0c\n\x04\x64\x61ta\x18\x02 \x01(\t\x12\x10\n\x08username\x18\x03 \x01(\t\x12\x14\n\x0cverification\x18\x04 \x01(\t2@\n\x16\x46\x61\x63\x65RecognitionService\x12&\n\x0f\x46\x61\x63\x65Recognition\x12\x08.Request\x1a\t.Responseb\x06proto3')



_REQUEST = DESCRIPTOR.message_types_by_name['Request']
_RESPONSE = DESCRIPTOR.message_types_by_name['Response']
Request = _reflection.GeneratedProtocolMessageType('Request', (_message.Message,), {
  'DESCRIPTOR' : _REQUEST,
  '__module__' : 'facial_recognition_pb2'
  # @@protoc_insertion_point(class_scope:Request)
  })
_sym_db.RegisterMessage(Request)

Response = _reflection.GeneratedProtocolMessageType('Response', (_message.Message,), {
  'DESCRIPTOR' : _RESPONSE,
  '__module__' : 'facial_recognition_pb2'
  # @@protoc_insertion_point(class_scope:Response)
  })
_sym_db.RegisterMessage(Response)

_FACERECOGNITIONSERVICE = DESCRIPTOR.services_by_name['FaceRecognitionService']
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _REQUEST._serialized_start=28
  _REQUEST._serialized_end=106
  _RESPONSE._serialized_start=108
  _RESPONSE._serialized_end=189
  _FACERECOGNITIONSERVICE._serialized_start=191
  _FACERECOGNITIONSERVICE._serialized_end=255
# @@protoc_insertion_point(module_scope)
