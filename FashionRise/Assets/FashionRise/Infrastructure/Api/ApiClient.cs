using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;

namespace FashionRise.Infrastructure.Api
{
    /// <summary>
    /// Shared HTTP client: base URL, bearer auth from <see cref="TokenStorageService"/>, JSON + multipart.
    /// </summary>
    public sealed class ApiClient : IDisposable
    {
        readonly ApiConfig _config;
        readonly TokenStorageService _tokens;
        readonly HttpClient _http;

        public ApiClient(ApiConfig config, TokenStorageService tokens)
        {
            _config = config;
            _tokens = tokens;
            _http = new HttpClient { Timeout = TimeSpan.FromSeconds(Math.Max(5, config.RequestTimeoutSeconds)) };
        }

        public void Dispose() => _http.Dispose();

        string AbsoluteUrl(string relativePath)
        {
            var root = _config.BaseUrl.TrimEnd('/');
            var path = relativePath.TrimStart('/');
            return $"{root}/{path}";
        }

        void AssertOnline()
        {
            if (_config.OfflineModePlaceholder)
                throw new ApiException(0, "Offline mode (placeholder): request not sent.");
        }

        /// <summary>Retry placeholder — returns the same task.</summary>
        public Task<T> WithRetryPlaceholder<T>(Func<Task<T>> send) => send();

        void ApplyAuth(HttpRequestMessage msg, bool useBearer)
        {
            msg.Headers.Authorization = null;
            if (!useBearer)
                return;
            var t = _tokens.AccessToken;
            if (!string.IsNullOrEmpty(t))
                msg.Headers.Authorization = new AuthenticationHeaderValue("Bearer", t);
        }

        public async Task<T> GetJsonAsync<T>(string relativePath, CancellationToken ct,
            bool useBearer = true)
        {
            AssertOnline();
            return await WithRetryPlaceholder(async () =>
            {
                using var msg = new HttpRequestMessage(HttpMethod.Get, AbsoluteUrl(relativePath));
                ApplyAuth(msg, useBearer);
                using var resp = await _http.SendAsync(msg, ct).ConfigureAwait(false);
                var body = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (!resp.IsSuccessStatusCode)
                    throw ApiException.FromHttpResponse(resp, body);
                return JsonConvert.DeserializeObject<T>(body, ApiJson.Settings)
                       ?? throw new ApiException((int)resp.StatusCode, "Empty JSON body", body);
            }).ConfigureAwait(false);
        }

        public async Task<TResponse> PostJsonAsync<TResponse>(string relativePath, object body,
            CancellationToken ct, bool useBearer = false)
        {
            AssertOnline();
            return await WithRetryPlaceholder(async () =>
            {
                var json = JsonConvert.SerializeObject(body, ApiJson.Settings);
                using var msg = new HttpRequestMessage(HttpMethod.Post, AbsoluteUrl(relativePath))
                {
                    Content = new StringContent(json, Encoding.UTF8, "application/json")
                };
                ApplyAuth(msg, useBearer);
                using var resp = await _http.SendAsync(msg, ct).ConfigureAwait(false);
                var respBody = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (!resp.IsSuccessStatusCode)
                    throw ApiException.FromHttpResponse(resp, respBody);
                return JsonConvert.DeserializeObject<TResponse>(respBody, ApiJson.Settings)
                       ?? throw new ApiException((int)resp.StatusCode, "Empty JSON body", respBody);
            }).ConfigureAwait(false);
        }

        public async Task<TResponse> PutJsonAsync<TResponse>(string relativePath, object body,
            CancellationToken ct, bool useBearer = true)
        {
            AssertOnline();
            return await WithRetryPlaceholder(async () =>
            {
                var json = JsonConvert.SerializeObject(body, ApiJson.Settings);
                using var msg = new HttpRequestMessage(HttpMethod.Put, AbsoluteUrl(relativePath))
                {
                    Content = new StringContent(json, Encoding.UTF8, "application/json")
                };
                ApplyAuth(msg, useBearer);
                using var resp = await _http.SendAsync(msg, ct).ConfigureAwait(false);
                var respBody = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (!resp.IsSuccessStatusCode)
                    throw ApiException.FromHttpResponse(resp, respBody);
                return JsonConvert.DeserializeObject<TResponse>(respBody, ApiJson.Settings)
                       ?? throw new ApiException((int)resp.StatusCode, "Empty JSON body", respBody);
            }).ConfigureAwait(false);
        }

        public async Task DeleteAsync(string relativePath, CancellationToken ct, bool useBearer = true)
        {
            AssertOnline();
            await WithRetryPlaceholder(async () =>
            {
                using var msg = new HttpRequestMessage(HttpMethod.Delete, AbsoluteUrl(relativePath));
                ApplyAuth(msg, useBearer);
                using var resp = await _http.SendAsync(msg, ct).ConfigureAwait(false);
                if (resp.StatusCode == System.Net.HttpStatusCode.NoContent)
                    return true;
                var respBody = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (!resp.IsSuccessStatusCode)
                    throw ApiException.FromHttpResponse(resp, respBody);
                return true;
            }).ConfigureAwait(false);
        }

        /// <summary>POST expecting 204 No Content (e.g. gallery like).</summary>
        public async Task PostExpectNoContentAsync(string relativePath, object? body, CancellationToken ct,
            bool useBearer = true)
        {
            AssertOnline();
            await WithRetryPlaceholder(async () =>
            {
                using var msg = new HttpRequestMessage(HttpMethod.Post, AbsoluteUrl(relativePath));
                var json = body == null ? "{}" : JsonConvert.SerializeObject(body, ApiJson.Settings);
                msg.Content = new StringContent(json, Encoding.UTF8, "application/json");
                ApplyAuth(msg, useBearer);
                using var resp = await _http.SendAsync(msg, ct).ConfigureAwait(false);
                if (resp.StatusCode == System.Net.HttpStatusCode.NoContent)
                    return true;
                var respBody = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (!resp.IsSuccessStatusCode)
                    throw ApiException.FromHttpResponse(resp, respBody);
                return true;
            }).ConfigureAwait(false);
        }

        public async Task<TResponse> PostMultipartImageAsync<TResponse>(string relativePath,
            byte[] fileBytes, string fileName, string? contentType, CancellationToken ct)
        {
            AssertOnline();
            return await WithRetryPlaceholder(async () =>
            {
                using var content = new MultipartFormDataContent();
                var ctVal = string.IsNullOrEmpty(contentType) ? "application/octet-stream" : contentType;
                var fileContent = new ByteArrayContent(fileBytes);
                fileContent.Headers.ContentType = MediaTypeHeaderValue.Parse(ctVal);
                content.Add(fileContent, "file", fileName);

                using var msg = new HttpRequestMessage(HttpMethod.Post, AbsoluteUrl(relativePath))
                {
                    Content = content
                };
                ApplyAuth(msg, true);
                using var resp = await _http.SendAsync(msg, ct).ConfigureAwait(false);
                var respBody = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (!resp.IsSuccessStatusCode)
                    throw ApiException.FromHttpResponse(resp, respBody);
                return JsonConvert.DeserializeObject<TResponse>(respBody, ApiJson.Settings)
                       ?? throw new ApiException((int)resp.StatusCode, "Empty JSON body", respBody);
            }).ConfigureAwait(false);
        }

        /// <summary>Waits briefly for Unity screenshot file to appear on disk.</summary>
        public static async Task<byte[]?> ReadFileWhenReadyAsync(string path, CancellationToken ct,
            int maxWaitMs = 4000)
        {
            var deadline = DateTime.UtcNow.AddMilliseconds(maxWaitMs);
            while (DateTime.UtcNow < deadline)
            {
                ct.ThrowIfCancellationRequested();
                try
                {
                    if (File.Exists(path))
                        return await File.ReadAllBytesAsync(path, ct).ConfigureAwait(false);
                }
                catch
                {
                    /* file may be locked briefly */
                }

                await Task.Delay(100, ct).ConfigureAwait(false);
            }

            return null;
        }
    }
}
