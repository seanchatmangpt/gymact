defmodule GymactPaaS.Repo do
  @moduledoc "PostgreSQL projection target. Connection authority is supplied by the deployment environment."

  use AshPostgres.Repo,
    otp_app: :gymact_paas,
    warn_on_missing_ash_functions?: false

  def min_pg_version do
    %Version{major: 16, minor: 0, patch: 0, pre: []}
  end

  def installed_extensions, do: ["uuid-ossp"]
end
