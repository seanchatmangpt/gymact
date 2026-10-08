defmodule GymactPaaS.MixProject do
  use Mix.Project

  @ash_r2rml_ref "0d5320f6c5e9a43bb3e8dcb0f30d301b1ebb64d7"

  def project do
    [
      app: :gymact_paas,
      version: "26.8.22",
      elixir: "~> 1.18",
      elixirc_paths: elixirc_paths(),
      start_permanent: Mix.env() == :prod,
      deps: deps(),
      aliases: [verify: ["compile --warnings-as-errors", "gymact.paas.generate", "compile --force --warnings-as-errors", "test"]]
    ]
  end

  def application do
    [extra_applications: [:logger, :crypto]]
  end

  defp elixirc_paths, do: ["lib", "generated/ash"]

  defp deps do
    [
      {:ash, "~> 3.0 and >= 3.28.0"},
      {:ash_postgres, "~> 2.0"},
      {:ash_r2rml,
       git: "https://github.com/seanchatmangpt/ash_r2rml.git",
       ref: @ash_r2rml_ref,
       app: false}
    ]
  end
end
