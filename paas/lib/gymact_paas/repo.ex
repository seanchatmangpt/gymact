defmodule GymactPaaS.Repo do
  @moduledoc "PostgreSQL projection target. Connection authority is supplied by the deployment environment."

  use AshPostgres.Repo,
    otp_app: :gymact_paas

  def installed_extensions, do: ["uuid-ossp"]
end
