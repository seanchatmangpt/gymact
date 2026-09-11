ExUnit.start()

unless System.get_env("GYMACT_CHICAGO") == "1" do
  ExUnit.configure(exclude: [:chicago])
end
