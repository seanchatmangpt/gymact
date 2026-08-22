from .receipts import Receipt, digest_value


def replay_matches(
    receipt: Receipt, observed_input: object, observed_output: object
) -> bool:
    input_matches = receipt.input_digest == digest_value(observed_input)
    output_matches = receipt.output_digest == digest_value(observed_output)
    return input_matches and output_matches
