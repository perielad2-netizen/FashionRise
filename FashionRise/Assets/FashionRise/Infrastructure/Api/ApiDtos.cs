using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace FashionRise.Infrastructure.Api
{
    [Serializable]
    public sealed class TokenResponseDto
    {
        public string AccessToken { get; set; } = "";
        public string RefreshToken { get; set; } = "";
        public string TokenType { get; set; } = "bearer";
    }

    [Serializable]
    public sealed class UserReadDto
    {
        public Guid Id { get; set; }
        public string Email { get; set; } = "";
        public string Username { get; set; } = "";
        public bool IsActive { get; set; }
        public bool IsAdmin { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    [Serializable]
    public sealed class FollowStatusReadDto
    {
        [JsonProperty("user_id")]
        public Guid UserId { get; set; }

        [JsonProperty("following")]
        public bool Following { get; set; }
    }

    [Serializable]
    public sealed class ProfileReadDto
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public string DisplayName { get; set; } = "";
        public string? Bio { get; set; }
        public string? AvatarUrl { get; set; }
        public string? CoverUrl { get; set; }
        public List<object> StyleTags { get; set; } = new();
        public int DesignsCount { get; set; }
        public int PublishedCount { get; set; }
        public int FollowersCount { get; set; }
        public int LikesReceivedCount { get; set; }
        public double? RatingAverage { get; set; }
        public int RatingCount { get; set; }
        public double ReputationScore { get; set; }
        public string ReputationTier { get; set; } = "";
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }

    [Serializable]
    public sealed class DesignReadDto
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public string Title { get; set; } = "";
        public string? Description { get; set; }
        public string GarmentCategory { get; set; } = "";
        public Guid? TemplateId { get; set; }
        public Guid? MaterialId { get; set; }
        public Guid? ColorPaletteId { get; set; }
        public JObject DesignData { get; set; } = new();
        [JsonProperty("metadata")]
        public JObject Metadata { get; set; } = new();
        public string Visibility { get; set; } = "";
        public string Status { get; set; } = "";
        public string ModerationStatus { get; set; } = "";
        public JArray? ModerationLabels { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }

    [Serializable]
    public sealed class DesignRevisionReadDto
    {
        public Guid Id { get; set; }
        public Guid DesignId { get; set; }
        public Guid UserId { get; set; }
        public int RevisionNumber { get; set; }
        public JObject DesignData { get; set; } = new();
        public string? Notes { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    [Serializable]
    public sealed class MaterialReadDto
    {
        public Guid Id { get; set; }
        public string Name { get; set; } = "";
        public string Family { get; set; } = "";
        public string? Description { get; set; }
        public double? SheenLevel { get; set; }
        public double? SoftnessLevel { get; set; }
        public string? WeightClass { get; set; }
        public string? DrapeCharacter { get; set; }
        public double? StretchLevel { get; set; }
        public int? LuxuryScore { get; set; }
        public JArray SeasonTags { get; set; } = new();
        public JArray RecommendedCategories { get; set; } = new();
        [JsonProperty("metadata")]
        public JObject Metadata { get; set; } = new();
        public string? TextureUrl { get; set; }
        public bool IsActive { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }

    [Serializable]
    public sealed class GarmentTemplateReadDto
    {
        public Guid Id { get; set; }
        public string Name { get; set; } = "";
        public string Category { get; set; } = "";
        public string? Description { get; set; }
        public JObject TemplateData { get; set; } = new();
        public string? PreviewUrl { get; set; }
        public bool IsActive { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }

    [Serializable]
    public sealed class ColorPaletteReadDto
    {
        public Guid Id { get; set; }
        public string Name { get; set; } = "";
        public JArray Colors { get; set; } = new();
        public JArray Tags { get; set; } = new();
        public bool IsActive { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }

    [Serializable]
    public sealed class GalleryReadDto
    {
        public Guid Id { get; set; }
        public Guid DesignId { get; set; }
        public Guid UserId { get; set; }
        public string Title { get; set; } = "";
        public string? ImageUrl { get; set; }
        public string Visibility { get; set; } = "";
        public double? RatingAverage { get; set; }
        public int RatingCount { get; set; }
        public int LikesCount { get; set; }
        public string ModerationStatus { get; set; } = "";
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        [JsonProperty("liked_by_me")]
        public bool? LikedByMe { get; set; }
    }

    [Serializable]
    public sealed class GalleryCommentReadDto
    {
        public Guid Id { get; set; }
        [JsonProperty("gallery_item_id")]
        public Guid GalleryItemId { get; set; }
        [JsonProperty("user_id")]
        public Guid UserId { get; set; }
        public string Body { get; set; } = "";
        [JsonProperty("moderation_status")]
        public string ModerationStatus { get; set; } = "";
        [JsonProperty("created_at")]
        public DateTime CreatedAt { get; set; }
    }

    [Serializable]
    public sealed class RatingReadDto
    {
        public Guid Id { get; set; }
        public Guid GalleryItemId { get; set; }
        public Guid UserId { get; set; }
        public int Score { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }

    [Serializable]
    public sealed class ExportReadDto
    {
        public Guid Id { get; set; }
        public Guid DesignId { get; set; }
        public Guid UserId { get; set; }
        public string ExportType { get; set; } = "";
        public string? FileUrl { get; set; }
        [JsonProperty("metadata")]
        public JObject Metadata { get; set; } = new();
        public DateTime CreatedAt { get; set; }
    }

    [Serializable]
    public sealed class ImageUploadResponseDto
    {
        public string Url { get; set; } = "";
        public string StoredKey { get; set; } = "";
    }

    [Serializable]
    public sealed class AIJobReadDto
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public Guid? DesignId { get; set; }
        public string JobType { get; set; } = "";
        public string Status { get; set; } = "";
        public JObject InputData { get; set; } = new();
        public JObject? ResultData { get; set; }
        public string? ErrorMessage { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }
}
