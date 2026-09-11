defmodule GymActEx.Client do
  @moduledoc """
  Thin BEAM projection of GymAct's canonical HTTP execution profile.

  This module deliberately owns no gym semantics. It transports the same JSON
  intents/results served by `gymact.surfaces.fastapi` and preserves non-2xx
  responses as evidence-bearing errors.
  """

  alias GymActEx.Error

  @canonical_operations ~w(discover materialize observe act verify checkpoint restore teardown)

  @enforce_keys [:base_url]
  defstruct base_url: nil, receive_timeout: 30_000

  @type t :: %__MODULE__{base_url: String.t(), receive_timeout: pos_integer()}
  @type result(value) :: {:ok, value} | {:error, Error.t()}

  @doc "Create a client. Defaults to `GYMACT_BASE_URL` or `http://127.0.0.1:8000`."
  @spec new(keyword()) :: t()
  def new(opts \\ []) do
    base_url =
      opts
      |> Keyword.get(:base_url, System.get_env("GYMACT_BASE_URL", "http://127.0.0.1:8000"))
      |> String.trim_trailing("/")

    %__MODULE__{
      base_url: base_url,
      receive_timeout: Keyword.get(opts, :receive_timeout, 30_000)
    }
  end

  @spec health(t()) :: result(map())
  def health(client), do: request(client, :get, "/health")

  @spec profile(t()) :: result(map())
  def profile(client), do: request(client, :get, "/profile")

  @spec contract(t()) :: result(map())
  def contract(client), do: request(client, :get, "/contract")

  @doc "Checks that the remote contract still exposes the eight generic GymAct operations."
  @spec contract_compatible?(t()) :: result(boolean())
  def contract_compatible?(client) do
    with {:ok, body} <- contract(client),
         operations when is_list(operations) <- value(body, "operations") do
      {:ok, Enum.sort(operations) == Enum.sort(@canonical_operations)}
    else
      nil -> {:ok, false}
      {:error, %Error{} = error} -> {:error, error}
      _ -> {:ok, false}
    end
  end

  @spec evidence(t()) :: result(map())
  def evidence(client), do: request(client, :get, "/evidence")

  @spec discover(t()) :: result([String.t()])
  def discover(client) do
    with {:ok, body} <- request(client, :get, "/providers"),
         providers when is_list(providers) <- value(body, "providers") do
      {:ok, providers}
    else
      {:error, %Error{} = error} -> {:error, error}
      _ -> {:error, shape_error(:get, url(client, "/providers"), "providers")}
    end
  end

  @spec materialize(t(), map()) :: result(map())
  def materialize(client, intent) when is_map(intent) do
    request(client, :post, "/episodes", json: intent)
  end

  @spec capabilities(t(), String.t()) :: result([map()])
  def capabilities(client, episode_id) do
    path = episode_path(episode_id, "/capabilities")

    with {:ok, body} <- request(client, :get, path),
         capabilities when is_list(capabilities) <- value(body, "capabilities") do
      {:ok, capabilities}
    else
      {:error, %Error{} = error} -> {:error, error}
      _ -> {:error, shape_error(:get, url(client, path), "capabilities")}
    end
  end

  @spec observe(t(), String.t()) :: result(map())
  def observe(client, episode_id) do
    request(client, :get, episode_path(episode_id, "/observations/latest"))
  end

  @doc """
  Invoke the generic GymAct `act` operation.

  The Python production surface marks this raw port deprecated because its
  canonical production DO path is `act_selected/3`. It remains the exact
  generic execution-profile operation and is useful for bounded reference
  gyms and cross-runtime equivalence tests.
  """
  @spec act(t(), String.t(), map()) :: result(map())
  def act(client, episode_id, intent) when is_map(intent) do
    request(client, :post, episode_path(episode_id, "/actions"), json: intent)
  end

  @doc "Canonical production DO path through GymAct's combinatorial decision court."
  @spec act_selected(t(), String.t(), map()) :: result(map())
  def act_selected(client, episode_id, request_body) when is_map(request_body) do
    request(client, :post, episode_path(episode_id, "/actions/selected"), json: request_body)
  end

  @doc "Compatibility BRCE actuation path exposed by the Python surface."
  @spec act_admitted(t(), String.t(), map()) :: result(map())
  def act_admitted(client, episode_id, request_body) when is_map(request_body) do
    request(client, :post, episode_path(episode_id, "/actions/admitted"), json: request_body)
  end

  @spec verify(t(), String.t(), map()) :: result(map())
  def verify(client, episode_id, expected) when is_map(expected) do
    request(client, :post, episode_path(episode_id, "/verify"), json: %{expected: expected})
  end

  @spec checkpoint(t(), String.t()) :: result(map())
  def checkpoint(client, episode_id) do
    path = episode_path(episode_id, "/checkpoint")

    with {:ok, body} <- request(client, :get, path),
         checkpoint when is_map(checkpoint) <- value(body, "checkpoint") do
      {:ok, checkpoint}
    else
      {:error, %Error{} = error} -> {:error, error}
      _ -> {:error, shape_error(:get, url(client, path), "checkpoint")}
    end
  end

  @spec restore(t(), String.t(), map(), keyword()) :: result(map())
  def restore(client, episode_id, checkpoint, opts \\ []) when is_map(checkpoint) do
    request(client, :post, episode_path(episode_id, "/restore"),
      json: %{checkpoint: checkpoint},
      params: authority_params(opts)
    )
  end

  @spec teardown(t(), String.t(), keyword()) :: result(map())
  def teardown(client, episode_id, opts \\ []) do
    request(client, :delete, episode_path(episode_id, ""), params: authority_params(opts))
  end

  defp request(%__MODULE__{} = client, method, path, opts \\ []) do
    request_url = url(client, path)

    req_opts = [
      method: method,
      url: request_url,
      params: Keyword.get(opts, :params, []),
      receive_timeout: client.receive_timeout,
      retry: false
    ]

    req_opts =
      case Keyword.fetch(opts, :json) do
        {:ok, body} -> Keyword.put(req_opts, :json, body)
        :error -> req_opts
      end

    case Req.request(req_opts) do
      {:ok, %Req.Response{status: status, body: body}} when status in 200..299 ->
        {:ok, body}

      {:ok, %Req.Response{status: status, body: body}} ->
        {:error,
         %Error{
           status: status,
           body: body,
           method: method,
           url: request_url,
           reason: :http_refusal
         }}

      {:error, reason} ->
        {:error,
         %Error{
           status: nil,
           body: nil,
           method: method,
           url: request_url,
           reason: reason
         }}
    end
  end

  defp episode_path(episode_id, suffix) do
    "/episodes/#{URI.encode_www_form(episode_id)}#{suffix}"
  end

  defp authority_params(opts) do
    case Keyword.get(opts, :authority_ref) do
      nil -> []
      authority_ref -> [authority_ref: authority_ref]
    end
  end

  defp url(%__MODULE__{base_url: base_url}, path), do: base_url <> path

  defp value(map, key) when is_map(map) do
    Map.get(map, key) || Map.get(map, String.to_existing_atom(key))
  rescue
    ArgumentError -> Map.get(map, key)
  end

  defp shape_error(method, request_url, expected_key) do
    %Error{
      status: nil,
      body: nil,
      method: method,
      url: request_url,
      reason: {:unexpected_response_shape, expected_key}
    }
  end
end
