# Copyright 2026 MSPbots.ai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Process settings. Holds no credentials: those arrive per request as headers."""

from pydantic_settings import BaseSettings, SettingsConfigDict

# Domotz serves each account from one regional cell. X-Domotz-Region accepts
# a short name, the cell's region name, or the API endpoint URL shown in the
# Domotz portal.
REGION_ALIASES: dict[str, str] = {
    "us": "us-east-1",
    "us-east-1": "us-east-1",
    "eu": "eu-west-1",
    "eu-west-1": "eu-west-1",
}
DEFAULT_REGION = "us-east-1"
API_URL_TEMPLATE = "https://api-{region}-cell-1.domotz.com/public-api/v1"
API_HOST_SUFFIX = ".domotz.com"


class Settings(BaseSettings):
    # extra="ignore": the runtime injects variables this project does not declare.
    model_config = SettingsConfigDict(extra="ignore")

    mcp_http_port: int = 8080
    mcp_http_host: str = "0.0.0.0"
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
