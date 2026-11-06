"""NAD and ABC adapter. Implements the academic-records port (contracts/ports/academic-records.yaml) and the Adapter
contract (contracts/ports/adapter.yaml). The hub finds it by the `eos.integration_adapters` entry point
(eos_nad.application.adapter:get_adapter). Operator view router: eos_nad.api.router.

v1.0 ships the manual channel: it validates a batch and writes the depository's own CSV upload file."""

__version__ = "0.3.0"  # keep equal to module.yaml (tests check)
