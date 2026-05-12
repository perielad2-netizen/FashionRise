using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Application;
using FashionRise.Services;
using UnityEngine;

namespace FashionRise.Infrastructure.Api
{
    /// <summary>
    /// Runs the inner PNG export, then uploads when <see cref="IAuthService.HasBackendSession"/>.
    /// Registers <c>POST /exports</c> unless <c>ExportRequest.SkipExportRegistration</c> is true (gallery preview URL only).
    /// </summary>
    public sealed class PublishingExportService : IExportService
    {
        readonly IExportService _inner;
        readonly UploadApiService _uploads;
        readonly ExportApiService _exports;
        readonly IAuthService _auth;

        public PublishingExportService(
            IExportService inner,
            UploadApiService uploads,
            ExportApiService exports,
            IAuthService auth)
        {
            _inner = inner;
            _uploads = uploads;
            _exports = exports;
            _auth = auth;
        }

        public async Task<ExportResult> ExportPngAsync(ExportRequest request,
            CancellationToken cancellationToken = default)
        {
            var result = await _inner.ExportPngAsync(request, cancellationToken).ConfigureAwait(true);
            if (!result.Success || result.Package == null)
                return result;

            if (!_auth.HasBackendSession)
            {
                result.Message += " Sign in with the API to upload exports.";
                return result;
            }

            try
            {
                var path = result.Package.LocalPngPath;
                // Android can finish writing the capture a few seconds after the call returns.
                var bytes = await ApiClient.ReadFileWhenReadyAsync(path, cancellationToken, maxWaitMs: 8000)
                    .ConfigureAwait(true);
                if (bytes == null || bytes.Length == 0)
                {
                    result.Message += " Could not read PNG file for upload.";
                    return result;
                }

                var fileName = Path.GetFileName(path);
                if (string.IsNullOrEmpty(fileName))
                    fileName = request.FileName + ".png";

                var url = await _uploads.UploadImageAsync(bytes, fileName, cancellationToken).ConfigureAwait(true);
                result.UploadedImageUrl = url;

                if (request.SkipExportRegistration)
                {
                    result.Message += " Uploaded preview (gallery only, no export row).";
                    return result;
                }

                await _exports.RegisterExportAsync(request.DesignId, "png", url, cancellationToken)
                    .ConfigureAwait(true);
                result.Message += " Uploaded and registered export.";
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"FashionRise export publish: {ex.Message}");
                result.Message += $" Upload failed: {ex.Message}";
            }

            return result;
        }
    }
}
