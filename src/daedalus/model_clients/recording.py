"""Recording wrapper for model clients."""

from pathlib import Path
from uuid import UUID

from daedalus.model_clients.client import ModelClient
from daedalus.model_clients.invocation_recorder import ModelInvocationRecorder
from daedalus.model_clients.types import ModelRequest, ModelResponse
from daedalus.orchestrator.run_lifecycle import utc_now


class RecordingModelClient:
    """ModelClient wrapper that records invocation metadata around an inner client."""

    def __init__(
        self,
        *,
        inner_client: ModelClient,
        recorder: ModelInvocationRecorder,
        step_id: UUID | None = None,
        agent_name: str | None = None,
        input_artifact_path: Path | None = None,
        output_artifact_path: Path | None = None,
    ) -> None:
        self._inner_client = inner_client
        self._recorder = recorder
        self._step_id = step_id
        self._agent_name = agent_name
        self._input_artifact_path = input_artifact_path
        self._output_artifact_path = output_artifact_path

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Delegate completion and record success or failure metadata."""
        started_at_utc = utc_now()
        try:
            response = self._inner_client.complete(request)
        except Exception as exc:
            completed_at_utc = utc_now()
            self._recorder.record_failure(
                request=request,
                error_message=str(exc),
                started_at_utc=started_at_utc,
                completed_at_utc=completed_at_utc,
                step_id=self._step_id,
                agent_name=self._agent_name,
                input_artifact_path=self._input_artifact_path,
                output_artifact_path=self._output_artifact_path,
            )
            raise

        completed_at_utc = utc_now()
        self._recorder.record_success(
            request=request,
            response=response,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            step_id=self._step_id,
            agent_name=self._agent_name,
            input_artifact_path=self._input_artifact_path,
            output_artifact_path=self._output_artifact_path,
        )
        return response
