defmodule GymactPaaS.ControlPlaneTest do
  use ExUnit.Case, async: true

  alias GymactPaaS.ControlPlane

  test "SELECT preserves all three hyperscaler candidates" do
    assert {:ok, selection} = ControlPlane.select(:compute)
    assert selection.action_class == :SELECT
    assert Enum.map(selection.candidates, & &1.provider) == [:aws, :azure, :gcp]
    assert Enum.uniq(Enum.map(selection.candidates, & &1.class_iri)) == [
             "http://schemas.ogf.org/occi/infrastructure#compute"
           ]
  end

  test "CONSTRUCT is receipted, replayable, and non-actuating" do
    assert {:ok, receipt} = ControlPlane.construct(:application, :aws)
    assert receipt.action_class == :CONSTRUCT
    assert receipt.actuation_performed == false
    assert ControlPlane.replay(receipt)
    refute ControlPlane.replay(%{receipt | capability: :storage})
  end

  test "direct DO is typed refusal and unknown capability fails closed" do
    assert {:error, %{code: :REFUSED_UNRECEIPTED_ACTUATION}} = ControlPlane.do(%{})
    assert {:error, %{code: :REFUSED_UNMAPPED_CAPABILITY}} = ControlPlane.select(:magic_database)
  end

  test "provider catalog is real RDF data, not executable resource code" do
    assert {:ok, graph} = ControlPlane.catalog_graph()
    assert RDF.Graph.triple_count(graph) > 30
  end
end
