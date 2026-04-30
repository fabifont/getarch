from hypothesis import given, settings
from hypothesis import strategies as st

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config

_MUTATIONS = st.fixed_dictionaries(
    {
        "reboot": st.booleans(),
        "bootloader.timeout_seconds": st.integers(min_value=0, max_value=120),
        "partitioning.efi_size_mib": st.integers(min_value=128, max_value=2048),
    },
)


@settings(max_examples=50, deadline=None)
@given(_MUTATIONS)
def test_random_mutations_remain_valid(mutations: dict[str, object]) -> None:
    payload: dict[str, object] = dict(EXAMPLES["minimal-ext4"])
    payload["reboot"] = mutations["reboot"]
    bl: dict[str, object] = dict(payload["bootloader"])  # type: ignore[arg-type]
    bl["timeout_seconds"] = mutations["bootloader.timeout_seconds"]
    payload["bootloader"] = bl
    part: dict[str, object] = dict(payload["partitioning"])  # type: ignore[arg-type]
    part["efi_size_mib"] = mutations["partitioning.efi_size_mib"]
    payload["partitioning"] = part
    Config.model_validate(payload)
