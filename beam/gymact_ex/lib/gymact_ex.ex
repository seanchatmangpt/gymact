defmodule GymActEx do
  @moduledoc """
  BEAM projection of the canonical GymAct execution profile.

  `GymActEx` is intentionally transport-thin: GymAct remains semantic authority.
  The Elixir surface does not reinterpret standing, authority, consequence,
  verification, or receipts.
  """

  alias GymActEx.Client

  def new(opts \\ []), do: Client.new(opts)

  defdelegate health(client), to: Client
  defdelegate profile(client), to: Client
  defdelegate contract(client), to: Client
  defdelegate contract_compatible?(client), to: Client
  defdelegate evidence(client), to: Client
  defdelegate discover(client), to: Client
  defdelegate materialize(client, intent), to: Client
  defdelegate capabilities(client, episode_id), to: Client
  defdelegate observe(client, episode_id), to: Client
  defdelegate act(client, episode_id, intent), to: Client
  defdelegate act_selected(client, episode_id, request), to: Client
  defdelegate act_admitted(client, episode_id, request), to: Client
  defdelegate verify(client, episode_id, expected), to: Client
  defdelegate checkpoint(client, episode_id), to: Client

  def restore(client, episode_id, checkpoint, opts \\ []),
    do: Client.restore(client, episode_id, checkpoint, opts)

  def teardown(client, episode_id, opts \\ []), do: Client.teardown(client, episode_id, opts)
end
