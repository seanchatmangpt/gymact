defmodule GymActEx.Error do
  @moduledoc """
  Transport or HTTP refusal returned by the canonical GymAct FastAPI surface.

  A non-2xx response remains data: callers receive the exact HTTP status and
  decoded response body instead of an exception that could erase standing or
  refusal evidence.
  """

  defexception [:status, :body, :method, :url, :reason]

  @type t :: %__MODULE__{
          status: non_neg_integer() | nil,
          body: term(),
          method: atom() | nil,
          url: String.t() | nil,
          reason: term()
        }

  @impl Exception
  def message(%__MODULE__{} = error) do
    "GymAct request failed method=#{inspect(error.method)} url=#{inspect(error.url)} " <>
      "status=#{inspect(error.status)} reason=#{inspect(error.reason)} body=#{inspect(error.body)}"
  end
end
