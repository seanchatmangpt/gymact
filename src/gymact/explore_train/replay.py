from .receipts import Receipt, digest_value


def replay_matches(receipt: Receipt, observed_input: object, observed_output: object) -> bool:
    return receipt.input_digest == digest_value(observed_input) and receipt.output_digest == digest_value(observed_output)
