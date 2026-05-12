using System;
using System.Text;
using Newtonsoft.Json.Linq;

namespace FashionRise.Infrastructure.Api
{
    /// <summary>Formats <see cref="AIJobReadDto.ResultData"/> for in-app display (OpenAI structured JSON, stub, errors).</summary>
    public static class AiJobResultFormatter
    {
        public static string? FormatJobBody(string status, JObject? resultData, string? errorMessage)
        {
            if (string.Equals(status, "failed", StringComparison.OrdinalIgnoreCase))
                return string.IsNullOrEmpty(errorMessage) ? "Job failed." : $"Error: {errorMessage}";

            if (resultData == null || resultData.Count == 0)
                return null;

            var sb = new StringBuilder();
            var msg = resultData.Value<string>("message");
            if (string.Equals(msg, "openai", StringComparison.Ordinal))
            {
                sb.AppendLine("Source: OpenAI");
                var model = resultData.Value<string>("model");
                if (!string.IsNullOrEmpty(model))
                    sb.AppendLine($"Model: {model}");
            }
            else if (!string.IsNullOrEmpty(msg) &&
                     msg.StartsWith("stub worker", StringComparison.OrdinalIgnoreCase))
            {
                sb.AppendLine("Source: stub worker (API has no OpenAI key for sketch jobs)");
            }

            var structured = resultData["structured"] as JObject;
            if (structured != null)
            {
                AppendBulletArray(sb, structured["cleanup_bullets"], "Cleanup tips");
                AppendBulletArray(sb, structured["polish_bullets"], "Polish directions");
                AppendSuggestions(sb, structured["suggestions"]);
            }

            var full = sb.ToString().TrimEnd();
            return string.IsNullOrEmpty(full) ? null : full;
        }

        static void AppendBulletArray(StringBuilder sb, JToken? arr, string heading)
        {
            if (arr is not JArray a || a.Count == 0)
                return;
            sb.AppendLine();
            sb.AppendLine(heading + ":");
            foreach (var x in a)
            {
                var t = x.Type == JTokenType.String ? x.Value<string>() : x?.ToString();
                if (!string.IsNullOrWhiteSpace(t))
                    sb.AppendLine($"  - {t.Trim()}");
            }
        }

        static void AppendSuggestions(StringBuilder sb, JToken? arr)
        {
            if (arr is not JArray a || a.Count == 0)
                return;
            sb.AppendLine();
            sb.AppendLine("Style suggestions:");
            foreach (var item in a)
            {
                if (item is not JObject o)
                    continue;
                var title = o.Value<string>("title")?.Trim();
                var desc = o.Value<string>("description")?.Trim();
                if (string.IsNullOrEmpty(title) && string.IsNullOrEmpty(desc))
                    continue;
                if (!string.IsNullOrEmpty(title))
                    sb.AppendLine($"  - {title}");
                if (!string.IsNullOrEmpty(desc))
                    sb.AppendLine($"    {desc}");
            }
        }
    }
}
