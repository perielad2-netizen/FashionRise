using System;

namespace FashionRise.Services
{
    [Serializable]
    public sealed class AuthResult
    {
        public bool Success { get; set; }
        public string UserId { get; set; } = "";
        public string Message { get; set; } = "";
    }
}
