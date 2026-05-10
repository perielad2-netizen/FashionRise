namespace FashionRise.Infrastructure.Api
{
    /// <summary>
    /// Typed API result wrapper (success path vs error message).
    /// </summary>
    public sealed class ApiResponse<T>
    {
        public bool Success { get; set; }
        public T? Value { get; set; }
        public string? ErrorMessage { get; set; }

        public static ApiResponse<T> Ok(T value) => new() { Success = true, Value = value };

        public static ApiResponse<T> Fail(string message) => new() { Success = false, ErrorMessage = message };
    }
}
