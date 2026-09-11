defmodule GymactPaaS.Profile do
  @moduledoc """
  Closed Fortune-5 operational profile over public cloud/standards terms.

  This module is an application profile, never an application ontology. Every
  Ash resource class is owned by OGF OCCI or a public W3C/QUDT ontology. Local
  URNs identify only profile entries, SHACL shapes, and ABox instances.
  """

  @xsd_string "http://www.w3.org/2001/XMLSchema#string"
  @dct_identifier "http://purl.org/dc/terms/identifier"
  @dct_title "http://purl.org/dc/terms/title"
  @dct_description "http://purl.org/dc/terms/description"
  @skos_notation "http://www.w3.org/2004/02/skos/core#notation"

  @public_namespaces [
    "http://schemas.ogf.org/occi/",
    "http://www.w3.org/ns/dcat#",
    "http://www.w3.org/ns/prov#",
    "http://www.w3.org/ns/odrl/2/",
    "http://www.w3.org/ns/sosa/",
    "http://purl.org/net/p-plan#",
    "http://www.w3.org/ns/dqv#",
    "http://qudt.org/schema/qudt/",
    "http://www.w3.org/2006/time#",
    "http://www.w3.org/ns/org#"
  ]

  @resource_specs [
    {:OcciApplication, "http://schemas.ogf.org/occi/platform#application", "occi_applications"},
    {:OcciComponent, "http://schemas.ogf.org/occi/platform#component", "occi_components"},
    {:OcciCompute, "http://schemas.ogf.org/occi/infrastructure#compute", "occi_compute"},
    {:OcciNetwork, "http://schemas.ogf.org/occi/infrastructure#network", "occi_networks"},
    {:OcciStorage, "http://schemas.ogf.org/occi/infrastructure#storage", "occi_storage"},
    {:DcatCatalog, "http://www.w3.org/ns/dcat#Catalog", "dcat_catalogs"},
    {:DcatDataService, "http://www.w3.org/ns/dcat#DataService", "dcat_data_services"},
    {:DcatDataset, "http://www.w3.org/ns/dcat#Dataset", "dcat_datasets"},
    {:DcatDistribution, "http://www.w3.org/ns/dcat#Distribution", "dcat_distributions"},
    {:OdrlPolicy, "http://www.w3.org/ns/odrl/2/Policy", "odrl_policies"},
    {:ProvActivity, "http://www.w3.org/ns/prov#Activity", "prov_activities"},
    {:ProvEntity, "http://www.w3.org/ns/prov#Entity", "prov_entities"},
    {:SosaPlatform, "http://www.w3.org/ns/sosa/Platform", "sosa_platforms"},
    {:SosaObservation, "http://www.w3.org/ns/sosa/Observation", "sosa_observations"},
    {:SosaActuation, "http://www.w3.org/ns/sosa/Actuation", "sosa_actuations"},
    {:PplanPlan, "http://purl.org/net/p-plan#Plan", "pplan_plans"},
    {:PplanStep, "http://purl.org/net/p-plan#Step", "pplan_steps"},
    {:DqvQualityMeasurement, "http://www.w3.org/ns/dqv#QualityMeasurement", "dqv_measurements"},
    {:QudtQuantityValue, "http://qudt.org/schema/qudt/QuantityValue", "qudt_quantity_values"},
    {:TimeInterval, "http://www.w3.org/2006/time#Interval", "time_intervals"},
    {:OrgOrganizationalUnit, "http://www.w3.org/ns/org#OrganizationalUnit", "org_units"}
  ]

  def public_namespaces, do: @public_namespaces
  def resource_specs, do: @resource_specs

  def profile do
    %{
      ontology_hash: "sha256:" <> digest(public_class_inventory()),
      profile_hash: "sha256:" <> digest_file(profile_path()),
      shacl_hash: "sha256:" <> digest_file(profile_path()),
      resources: Enum.map(@resource_specs, &resource/1)
    }
  end

  def profile_path, do: Application.app_dir(:gymact_paas, "priv/semantic/fortune5-cloud-profile.ttl")
  def catalog_path, do: Application.app_dir(:gymact_paas, "priv/semantic/provider-catalog.ttl")

  def public_class_iri?(iri) when is_binary(iri) do
    Enum.any?(@public_namespaces, &String.starts_with?(iri, &1))
  end

  def public_class_iri?(_), do: false

  defp resource({suffix, class_iri, table}) do
    slug = suffix |> Atom.to_string() |> Macro.underscore() |> String.replace("_", "-")

    %{
      iri: "urn:gymact:paas:projection:#{slug}",
      class_iri: class_iri,
      shape_iri: "urn:gymact:paas:shape:#{slug}",
      module: "GymactPaaS.Generated.#{suffix}",
      repo_module: "GymactPaaS.Repo",
      table: table,
      subject_template: "urn:gymact:paas:instance:#{slug}:{id}",
      identities: [%{name: :semantic_identity, keys: [:id], primary?: true}],
      attributes: common_attributes(),
      provenance: %{
        source: class_iri,
        authority: standard_authority(class_iri),
        projection: :ash_r2rml
      }
    }
  end

  defp common_attributes do
    [
      attribute(:id, @dct_identifier, 1, false, true),
      attribute(:title, @dct_title, 1, false, false),
      attribute(:description, @dct_description, 0, true, false),
      attribute(:kind, @skos_notation, 0, true, false)
    ]
  end

  defp attribute(name, predicate, min_count, nullable, identity?) do
    %{
      name: name,
      column: Atom.to_string(name),
      predicate_iri: predicate,
      datatype_iri: @xsd_string,
      min_count: min_count,
      max_count: 1,
      nullable: nullable,
      identity?: identity?
    }
  end

  defp standard_authority("http://schemas.ogf.org/occi/" <> _), do: :ogf
  defp standard_authority("http://qudt.org/" <> _), do: :qudt
  defp standard_authority(_), do: :w3c

  defp public_class_inventory do
    @resource_specs
    |> Enum.map(fn {_name, iri, _table} -> iri end)
    |> Enum.sort()
    |> Enum.join("\n")
  end

  defp digest_file(path), do: path |> File.read!() |> digest()
  defp digest(data), do: :crypto.hash(:sha256, data) |> Base.encode16(case: :lower)
end
