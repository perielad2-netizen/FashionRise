using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;

namespace FashionRise.Infrastructure.Api
{
    /// <summary>
    /// JSON settings aligned with FastAPI default snake_case payloads.
    /// </summary>
    public static class ApiJson
    {
        public static readonly JsonSerializerSettings Settings = new()
        {
            NullValueHandling = NullValueHandling.Ignore,
            ContractResolver = new DefaultContractResolver
            {
                NamingStrategy = new SnakeCaseNamingStrategy()
            }
        };

        public static JsonSerializer Serializer => JsonSerializer.Create(Settings);
    }
}
