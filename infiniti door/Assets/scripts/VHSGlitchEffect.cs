using UnityEngine;

[ExecuteInEditMode]
[RequireComponent(typeof(Camera))]
public class VHSGlitchEffect : MonoBehaviour
{
    public Shader glitchShader;
    private Material glitchMaterial;

    [Range(0f, 1f)]
    public float intensity = 0.7f;

    [Range(0f, 0.05f)]
    public float colorShift = 0.03f;

    [Range(0f, 1f)]
    public float noiseAmount = 0.8f;

    [Range(0f, 1f)]
    public float scanlineAmount = 0.8f;

    [Range(0f, 0.05f)]
    public float jitterAmount = 0.03f;

    void OnEnable()
    {
        if (glitchShader == null)
            glitchShader = Shader.Find("Hidden/VHSGlitch");

        if (glitchShader != null)
            glitchMaterial = new Material(glitchShader);
    }

    void OnRenderImage(RenderTexture source, RenderTexture destination)
    {
        if (glitchMaterial == null)
        {
            Graphics.Blit(source, destination);
            return;
        }

        glitchMaterial.SetFloat("_Intensity", intensity);
        glitchMaterial.SetFloat("_ColorShift", colorShift);
        glitchMaterial.SetFloat("_NoiseAmount", noiseAmount);
        glitchMaterial.SetFloat("_ScanlineAmount", scanlineAmount);
        glitchMaterial.SetFloat("_JitterAmount", jitterAmount);

        Graphics.Blit(source, destination, glitchMaterial);
    }
}