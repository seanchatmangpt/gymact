defmodule GymactPaaS.Fortune5ProfileTest do
  use ExUnit.Case, async: true

  alias GymactPaaS.{ControlPlane, Profile}

  test "every Ash resource is an AshR2RML projection of a public ontology class" do
    assert {:ok, compilation} = ControlPlane.compile()
    assert compilation.status == :PARTIAL_ALIVE
    assert compilation.standing == :constructed_not_actuated
    assert compilation.receipt.classes_admitted == 21

    Enum.each(compilation.ir.resources, fn resource ->
      assert Profile.public_class_iri?(resource.class_iri)
      refute String.starts_with?(resource.class_iri, "urn:gymact:")
      assert String.starts_with?(resource.module, "GymactPaaS.Generated.")
      assert compilation.ash_source =~ "defmodule #{resource.module}"
    end)

    assert compilation.ash_source =~ "AshPostgres.DataLayer"
    assert compilation.receipt.cutover_authority == :UNAUTHORIZED
    assert :cutover_authority in compilation.receipt.blocked
  end

  test "ggen bundle is deterministic and owns generated projection paths" do
    assert {:ok, first} = ControlPlane.ggen_bundle()
    assert {:ok, second} = ControlPlane.ggen_bundle()

    assert first.receipt.ir_sha256 == second.receipt.ir_sha256
    assert first.receipt.ash_sha256 == second.receipt.ash_sha256
    assert first.files == second.files
    assert is_binary(first.files["generated/ash/ontology_resources.ex"])
    assert is_binary(first.files["generated/sql/semantic_schema.sql"])
    assert is_binary(first.files["priv/r2rml/mapping.ttl"])
  end

  test "local semantic inputs define profile, shapes, and ABox only" do
    for path <- [Profile.profile_path(), Profile.catalog_path()] do
      source = File.read!(path)
      refute source =~ ~r/urn:gymact:[^\s>]+\s+(?:a|rdf:type)\s+(?:owl:Class|rdfs:Class)/
      refute source =~ ~r/urn:gymact:[^\s>]+\s+(?:a|rdf:type)\s+owl:(?:ObjectProperty|DatatypeProperty)/
    end
  end
end
