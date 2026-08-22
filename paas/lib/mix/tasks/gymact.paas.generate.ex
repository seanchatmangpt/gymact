defmodule Mix.Tasks.Gymact.Paas.Generate do
  use Mix.Task

  @shortdoc "Materialize deterministic AshR2RML projections from the admitted PaaS profile"
  @allowed_prefixes ["generated/", "priv/r2rml/", "receipts/"]

  @impl Mix.Task
  def run(_args) do
    Mix.Task.run("app.start")

    case GymactPaaS.ControlPlane.ggen_bundle() do
      {:ok, %{files: files, receipt: receipt}} ->
        Enum.each(files, &write_projection/1)
        Mix.shell().info("PAAS_PARTIAL_ALIVE receipt=#{receipt.ir_sha256}")

      {:error, reason} ->
        Mix.raise("PaaS semantic compilation refused: #{inspect(reason)}")
    end
  end

  defp write_projection({relative, content}) do
    unless Enum.any?(@allowed_prefixes, &String.starts_with?(relative, &1)) do
      Mix.raise("REFUSED_GENERATOR_PATH_ESCAPE: #{relative}")
    end

    path = Path.expand(relative, File.cwd!())
    root = Path.expand(File.cwd!()) <> Path.sep()

    unless String.starts_with?(path, root) do
      Mix.raise("REFUSED_GENERATOR_PATH_ESCAPE: #{relative}")
    end

    File.mkdir_p!(Path.dirname(path))
    File.write!(path, content)
  end
end
