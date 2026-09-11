defmodule GymActEx.MixProject do
  use Mix.Project

  def project do
    [
      app: :gymact_ex,
      version: "26.8.8",
      elixir: "~> 1.16",
      start_permanent: Mix.env() == :prod,
      deps: deps(),
      aliases: aliases(),
      docs: [main: "readme", extras: ["README.md"]]
    ]
  end

  def application do
    [extra_applications: [:logger, :ssl]]
  end

  defp deps do
    [
      {:req, "~> 0.5"}
    ]
  end

  defp aliases do
    [
      chicago: ["test --include chicago"]
    ]
  end
end
