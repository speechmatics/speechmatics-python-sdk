"""
Sync example showing batch transcription with the blocking Client.

No event loop is involved. This also demonstrates synchronous transcription
(the ``wait`` parameter), where the server holds the request open until the
transcript is ready, so one request replaces submit + poll + fetch.
"""

import os

from speechmatics.batch import Client
from speechmatics.batch import FormatType
from speechmatics.batch import JobConfig
from speechmatics.batch import JobStatus
from speechmatics.batch import JobType
from speechmatics.batch import Transcript
from speechmatics.batch import TranscriptionConfig

audio_file = os.getenv("AUDIO_FILE_PATH", os.path.join(os.path.dirname(__file__), "../example1.wav"))

# Seconds to let the server wait for the job before falling back to polling.
wait_seconds = int(os.getenv("WAIT_SECONDS", "60"))


def job_config() -> JobConfig:
    return JobConfig(
        type=JobType.TRANSCRIPTION,
        transcription_config=TranscriptionConfig(language="en", enable_entities=True),
    )


def transcribe_in_one_request(client: Client) -> None:
    """Submit and get the transcript back in a single request."""
    print("\n1) Synchronous transcription (one request)")
    print(f"   Submitting {audio_file} with wait={wait_seconds}s")

    job = client.submit_job(audio_file, config=job_config(), wait=wait_seconds)
    print(f"   Job {job.id} came back with status: {job.status.value}")

    if job.status == JobStatus.DONE and job.transcript is not None:
        print("   The transcript was embedded in the submit response, so no further calls were needed.")
        print(f"   Transcript: {job.transcript.transcript_text}")
    elif job.status == JobStatus.DONE:
        # Finished, but the response carried no transcript: one extra call.
        print("   Job finished but no transcript was embedded; fetching it separately.")
        print(f"   Transcript: {client.get_transcript(job.id).transcript_text}")
    else:
        # The wait elapsed before the job finished, which is expected for longer audio.
        # No timeout here: how long transcription takes depends on the audio's
        # length, so the example doesn't guess at a deadline.
        print(f"   Still running after {wait_seconds}s, falling back to polling.")
        result = client.wait_for_completion(job.id, polling_interval=2.0, timeout=None)
        print(f"   Transcript: {result.transcript_text}")


def transcribe_as_plain_text(client: Client) -> None:
    """The same thing in one call, asking for plain text instead of JSON."""
    print("\n2) One call via transcribe(), plain text output")

    text = client.transcribe(
        audio_file,
        config=job_config(),
        format_type=FormatType.TXT,
        wait=wait_seconds,
        timeout=None,
    )
    print(f"   Transcript: {text}")


def submit_and_poll(client: Client) -> None:
    """The classic flow, for comparison: submit, then poll until done."""
    print("\n3) Classic flow: submit, then poll")

    job = client.submit_job(audio_file, config=job_config())
    print(f"   Job submitted: {job.id}")

    result = client.wait_for_completion(job.id, polling_interval=2.0, timeout=None)
    if isinstance(result, Transcript):
        print(f"   Transcript: {result.transcript_text}")
    else:
        print(f"   Transcript: {result}")


def main() -> None:
    """Run sync batch transcription examples."""
    with Client(api_key=os.getenv("SPEECHMATICS_API_KEY")) as client:
        try:
            transcribe_in_one_request(client)
            transcribe_as_plain_text(client)
            submit_and_poll(client)

        except FileNotFoundError:
            print(f"Audio file not found: {audio_file}")
            print("Set AUDIO_FILE_PATH environment variable to specify audio file")

        except Exception as e:
            print(f"Transcription failed: {e}")


if __name__ == "__main__":
    main()
