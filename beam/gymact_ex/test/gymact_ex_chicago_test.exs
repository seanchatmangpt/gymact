defmodule GymActEx.ChicagoTest do
  use ExUnit.Case, async: false

  @moduletag :chicago

  @set_capability "urn:gymact:memory:capability:set"

  test "real Elixir client traverses the real Python GymAct execution profile" do
    base_url = System.fetch_env!("GYMACT_BASE_URL")
    client = GymActEx.new(base_url: base_url)
    run_id = Integer.to_string(System.unique_integer([:positive, :monotonic]))

    assert {:ok, %{"status" => "ALIVE"}} = GymActEx.health(client)
    assert {:ok, true} = GymActEx.contract_compatible?(client)

    assert {:ok, providers} = GymActEx.discover(client)
    assert "memory" in providers

    materialize_intent = %{
      provider: "memory",
      config: %{
        initial: %{healthy: false, generation: 0},
        requires_authority: false
      },
      idempotency_key: "gymact-ex-chicago-materialize-#{run_id}"
    }

    assert {:ok, materialized} = GymActEx.materialize(client, materialize_intent)
    assert materialized["accepted"] == true
    assert materialized["standing"] == "ALIVE"

    episode_id = get_in(materialized, ["episode", "episode_id"])
    assert is_binary(episode_id)

    on_exit(fn ->
      _ = GymActEx.teardown(client, episode_id)
    end)

    assert {:ok, capabilities} = GymActEx.capabilities(client, episode_id)
    assert Enum.any?(capabilities, &(&1["iri"] == @set_capability))

    assert {:ok, before} = GymActEx.observe(client, episode_id)
    assert before["state"] == %{"generation" => 0, "healthy" => false}

    act_intent = %{
      episode_id: episode_id,
      capability: @set_capability,
      payload: %{key: "healthy", value: true},
      idempotency_key: "gymact-ex-chicago-act-#{run_id}"
    }

    assert {:ok, acted} = GymActEx.act(client, episode_id, act_intent)
    assert acted["accepted"] == true
    assert acted["standing"] == "ALIVE"
    assert get_in(acted, ["observation", "state", "healthy"]) == true

    assert {:ok, verified} = GymActEx.verify(client, episode_id, %{healthy: true})
    assert verified["passed"] == true
    assert verified["observed"]["healthy"] == true

    assert {:ok, checkpoint} = GymActEx.checkpoint(client, episode_id)
    assert checkpoint["healthy"] == true

    mutate_after_checkpoint = %{
      episode_id: episode_id,
      capability: @set_capability,
      payload: %{key: "healthy", value: false},
      idempotency_key: "gymact-ex-chicago-mutate-#{run_id}"
    }

    assert {:ok, mutated} = GymActEx.act(client, episode_id, mutate_after_checkpoint)
    assert get_in(mutated, ["observation", "state", "healthy"]) == false

    assert {:ok, _restored} = GymActEx.restore(client, episode_id, checkpoint)
    assert {:ok, after_restore} = GymActEx.observe(client, episode_id)
    assert after_restore["state"]["healthy"] == true

    assert {:ok, teardown_result} = GymActEx.teardown(client, episode_id)
    assert teardown_result["operation"] == "teardown"
    assert teardown_result["standing"] == "ALIVE"

    assert {:ok, evidence} = GymActEx.evidence(client)
    assert evidence["verified"] == true
    assert is_list(evidence["records"])
    assert length(evidence["records"]) >= 5
  end
end
