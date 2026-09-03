defmodule GymactPaaS.ControlPlane do
  @moduledoc """
  Provider-neutral SELECT/CONSTRUCT surface for the GymAct Fortune-5 PaaS.

  It intentionally has no ambient DO authority. Provider choices remain an
  explicit reversible candidate set until a BRCE-authorized external actuator
  consumes a receipted construction.
  """

  alias GymactPaaS.Profile

  @providers [:aws, :azure, :gcp]
  @capability_classes %{
    application: "http://schemas.ogf.org/occi/platform#application",
    component: "http://schemas.ogf.org/occi/platform#component",
    compute: "http://schemas.ogf.org/occi/infrastructure#compute",
    network: "http://schemas.ogf.org/occi/infrastructure#network",
    storage: "http://schemas.ogf.org/occi/infrastructure#storage",
    data_service: "http://www.w3.org/ns/dcat#DataService",
    dataset: "http://www.w3.org/ns/dcat#Dataset"
  }

  def compile, do: AshR2RML.Compiler.compile(Profile.profile())
  def ggen_bundle, do: AshR2RML.Ggen.compile_bundle(Profile.profile())

  def select(capability) do
    with {:ok, class_iri} <- capability_class(capability) do
      candidates =
        Enum.map(@providers, fn provider ->
          %{
            provider: provider,
            class_iri: class_iri,
            catalog_subject: "urn:gymact:paas:catalog:#{provider}:#{capability}"
          }
        end)

      {:ok, %{action_class: :SELECT, capability: capability, candidates: candidates}}
    end
  end

  def construct(capability, provider) when provider in @providers do
    with {:ok, selection} <- select(capability),
         {:ok, candidate} <- fetch_provider(selection.candidates, provider) do
      body = %{
        action_class: :CONSTRUCT,
        actuation_performed: false,
        capability: capability,
        candidate: candidate,
        profile_hash: Profile.profile().profile_hash
      }

      {:ok, Map.put(body, :receipt_sha256, digest(body))}
    end
  end

  def construct(_capability, provider),
    do: {:error, refusal(:REFUSED_UNSUPPORTED_PROVIDER, %{provider: provider})}

  def replay(receipt) when is_map(receipt) do
    expected = Map.get(receipt, :receipt_sha256)
    body = Map.delete(receipt, :receipt_sha256)
    Map.get(receipt, :actuation_performed) == false and expected == digest(body)
  end

  def replay(_), do: false

  # `do` is an Elixir reserved keyword and cannot be used as a normal function
  # identifier.  Keep the architectural DO boundary explicit without smuggling
  # authority through parser tricks: callers ask to actuate and receive the same
  # typed fail-closed BRCE refusal.
  def actuate(_intent),
    do: {:error, refusal(:REFUSED_UNRECEIPTED_ACTUATION, %{authority: :brce_required})}

  def catalog_graph do
    RDF.Turtle.read_file(Profile.catalog_path())
  end

  defp capability_class(capability) do
    case Map.fetch(@capability_classes, capability) do
      {:ok, class_iri} -> {:ok, class_iri}
      :error -> {:error, refusal(:REFUSED_UNMAPPED_CAPABILITY, %{capability: capability})}
    end
  end

  defp fetch_provider(candidates, provider) do
    case Enum.find(candidates, &(&1.provider == provider)) do
      nil -> {:error, refusal(:REFUSED_UNSUPPORTED_PROVIDER, %{provider: provider})}
      candidate -> {:ok, candidate}
    end
  end

  defp refusal(code, detail), do: %{status: :REFUSED, code: code, detail: detail}

  defp digest(term) do
    term
    |> :erlang.term_to_binary([:deterministic])
    |> then(&:crypto.hash(:sha256, &1))
    |> Base.encode16(case: :lower)
  end
end
