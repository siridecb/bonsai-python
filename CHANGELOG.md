# Changelog

## 0.13.0
### Changed
- Simulator event processing moved to a background thread to keep the event loop unblocked.
### Removed
- Removed the asyncio event loop driver.
### Added
- Added sim_id field to protobuf.

## 0.12.1
### Fixed
- Fix namespace error causing crash for python 2.7.

## 0.12.0
### Added
- Add a function `logging_basic_config()` that can be called to setup a
very simple root logger to make it easy for simulators to setup logging
before calling into `bonsai.run_for_training_or_prediction()`. Most Bonsai
simulator samples will use this function. Advanced users who setup their
own python logging will not need to use this function.

### Fixed
- Fix a print statement that would output a confusing message about asyncio
not being imported even when asyncio isn't used. A warning will now be
logged only when appropriate.

## 0.11.2
### Changed
- Simplify pytest settings.

## 0.11.1
### Added
- Add more user friendly exception messages when encountering errors when
converting states from python dictionaries to protobuf messages.
- Add ability to pass command line arguments directly to the
method `run_for_training_or_prediction` as `*argv`. This is useful when
running a simulator from within another process.

### Changed
- Allow protobuf versions greater then 3.1.
- Anonymous protobuf descriptors (descriptors that have no name) were being
assigned a randomly generated name. Now they are all assigned the same
static name.

## 0.11.0
### Changed
- Update the way protobuf message classes are created from DescriptorProto
messages to be compatible with versions of protobuf beyond 3.1.

### Fixed
- Fix a bug that was causing the `--recording-file` command line argument
to be ignored.

## 0.10.1
### Changed
- Change test framework from nose2 to pytest.

## 0.10.0
### Added
- Add support for simulator ids. The Bonsai platform now supports connecting
multiple simulators when training a brain. This support requires all
simulators be assigned a random id. The `sim_id` field has been added to the
protobuf message protocol as part of this change.
- Add a preliminary, alternate version of a Simulator interface. The new
classes in support of this are in the file brain.py. This code is a very
early, initial implementation and is not recommended for use.

## 0.9.0
### Fixed
- Fix a memory leak when reconstituting protobuf classes by adding a
cache to the protobuf message builder.

### Removed
- Remove the `selection` field from the `SimulationSourceData` protobuf
message, as it is no longer used.

## 0.8.0
### Added
- Add code coverage configuration.
- Add a `selection` field to the `SimulationSourceData` protobuf message for
internal Bonsai platform use.

### Removed
- Remove the `MessageBuilder` class, but keep its reconstitute methods as
normal functions.
- Remove parsing of the `--headless` argument. This argument is now parsed
by the functionality in the bonsai-gym-common class.

## 0.7.1
### Added
- Add an error if API access key is missing.
- Add support for specifying required arguments via environment variables.

## 0.7.0
### Added
- Add support for specifying an access key using the `--access-key` command
line argument.

## 0.6.2
### Added
- Add support for internal Bonsai platform integration testing.

### Fixed
- Fix a bug which would cause KeyErrors raised when simulators return
incorrect state dictionaries to be incorrectly caught.

## 0.6.1
### Fixed
- Fix a bug which would cause certain KeyErrors to be incorrectly caught
as unexpected message errors.
- Fix some pylint errors.

## 0.6.0
### Added
- Add support for creating `Luminance` objects from additional data types.
- Add ability to support batches of predictions and states when
communicating with the Bonsai server.

### Changed
- Large refactor to better support internal Bonsai platform system testing.
This refactor adds asyncio support when using python 3.5.

### Fixed
- Fix a bug which could cause a simulator to hang when it should exit.

## 0.5.1
### Added
- Add ability to convert README.md into RST using pypandoc.

### Changed
- Restrict maximum protobuf version to 3.1.

### Fixed
- Fix a bug which would cause properly closed connections to issue a stack
trace, which makes it look like there was an error.

## 0.5.0
### Added
- Add support for python 2.7.

### Changed
- Use tornado instead of asyncio in order to support python 2.7.

## 0.4.0
### Added
- Add support for utilizing secure websocket connections.

### Changed
- Increase the minimum required version of bonsai-config to 0.3.0.

## 0.3.0
### Changed
- Change the bonsai-config dependency to use the PyPi version, instead
of directly relying upon the bonsai-config github repository.
- Specify an access key when forming websocket connections to Bonsai servers.

## 0.2.1
### Added
- Add a dependency on bonsai-config, and use the configuration data it
contains when forming connections to the bonsai server.

### Removed
- Remove code that manually reads the .bonsai file in favor of using the
code in the bonsai-config package.

## 0.2.0
### Added
- Add a `--headless` command line argument so that simulators can be run
without visualization.

## 0.1.0
### Added
- Initial release.
