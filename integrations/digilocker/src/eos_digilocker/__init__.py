"""DigiLocker adapter. Implements the certificate-issuance port (contracts/ports/certificate-issuance.yaml) and the
Adapter contract (contracts/ports/adapter.yaml). The hub finds it by the `eos.integration_adapters` entry point
(eos_digilocker.application.adapter:get_adapter). Operator view router: eos_digilocker.api.router."""

__version__ = "0.3.0"  # keep equal to module.yaml (tests check)
