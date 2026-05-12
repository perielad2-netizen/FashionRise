using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using Newtonsoft.Json.Linq;

namespace FashionRise.Infrastructure.Api
{
    public sealed class ApiException : Exception
    {
        public int StatusCode { get; }
        public string? ResponseBody { get; }

        public ApiException(int statusCode, string message, string? responseBody = null, Exception? inner = null)
            : base(message, inner)
        {
            StatusCode = statusCode;
            ResponseBody = responseBody;
        }

        public static ApiException FromHttpResponse(HttpResponseMessage response, string body)
        {
            var code = (int)response.StatusCode;
            var msg = TryExtractDetail(body) ?? response.ReasonPhrase ?? "Request failed";
            return new ApiException(code, msg, body);
        }

        /// <summary>FastAPI: <c>detail</c> string, or validation array with <c>msg</c> per item.</summary>
        static string? TryExtractDetail(string body)
        {
            if (string.IsNullOrWhiteSpace(body))
                return null;
            try
            {
                var jo = JObject.Parse(body);
                var detail = jo["detail"];
                return detail?.Type switch
                {
                    JTokenType.String => detail.Value<string>(),
                    JTokenType.Array => FormatValidationErrors((JArray)detail),
                    _ => detail?.Type == JTokenType.Object ? detail["msg"]?.Value<string>() : detail?.ToString()
                };
            }
            catch
            {
                return null;
            }
        }

        static string FormatValidationErrors(JArray arr)
        {
            var parts = new List<string>();
            foreach (var item in arr)
            {
                if (item is not JObject o)
                    continue;
                var msg = o["msg"]?.Value<string>();
                if (string.IsNullOrEmpty(msg))
                    continue;
                if (o["loc"] is JArray loc && loc.Count > 0)
                {
                    var lastTok = loc[loc.Count - 1];
                    var field = lastTok.Type == JTokenType.String
                        ? lastTok.Value<string>()
                        : lastTok.ToString();
                    if (!string.IsNullOrEmpty(field) && field != "body")
                        parts.Add($"{field}: {msg}");
                    else
                        parts.Add(msg);
                }
                else
                    parts.Add(msg);
            }

            return parts.Count > 0 ? string.Join("\n", parts) : arr.ToString();
        }

        public bool IsTimeout =>
            StatusCode == (int)HttpStatusCode.RequestTimeout || Message.Contains("timeout", StringComparison.OrdinalIgnoreCase);

        public bool IsRateLimited => StatusCode == (int)HttpStatusCode.TooManyRequests;
    }
}
