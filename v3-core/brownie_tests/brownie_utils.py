from contextlib import contextmanager

import brownie


@contextmanager
def brownie_reverts_fix(
    message=None,
):
    try:
        with brownie.reverts(message):
            yield
    except ValueError:
        pass
    except AssertionError as e:
        assert e.args[0] == f"Unexpected revert string 'None'\n"
    except Exception as e:
        assert isinstance(e, ValueError), f"Expected ValueError, got {e}"
