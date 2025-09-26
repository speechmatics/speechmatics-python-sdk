# Voice SDK Tests

You will need a `SPEECHMATICS_API_KEY` to run most of the tests, as they will use live transcription.

To run tests:

```bash
# Install dependencies
make install-dev

# Run tests without an API key (those needing live transcription will be skipped)
make test-voice

# Run all tests
SPEECHMATICS_API_KEY=your_api_key make voice-tests

# Run a specific test
SPEECHMATICS_API_KEY=your_api_key pytest -v -s tests/voice/test_03_conversation.py

# Run a specific sub-test
SPEECHMATICS_API_KEY=your_api_key pytest -v -s tests/voice/test_03_conversation.py::test_log_messages

# Run a specific test with logging
SPEECHMATICS_API_KEY=your_api_key SPEECHMATICS_SHOW_LOG=1 pytest -v -s tests/voice/test_03_conversation.py
```
