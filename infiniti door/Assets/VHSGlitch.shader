Shader "Hidden/VHSGlitch"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
        _Intensity ("Intensity", Range(0, 1)) = 0.3
        _ColorShift ("Color Shift", Range(0, 0.05)) = 0.01
        _NoiseAmount ("Noise Amount", Range(0, 1)) = 0.25
        _ScanlineAmount ("Scanline Amount", Range(0, 1)) = 0.35
        _JitterAmount ("Jitter Amount", Range(0, 0.05)) = 0.01
    }

    SubShader
    {
        Cull Off
        ZWrite Off
        ZTest Always

        Pass
        {
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _MainTex;

            float _Intensity;
            float _ColorShift;
            float _NoiseAmount;
            float _ScanlineAmount;
            float _JitterAmount;

            float rand(float2 co)
            {
                return frac(sin(dot(co.xy, float2(12.9898, 78.233))) * 43758.5453);
            }

            fixed4 frag(v2f_img i) : SV_Target
            {
                float2 uv = i.uv;
                float time = _Time.y;

                float lineNoise = rand(float2(floor(uv.y * 240.0), floor(time * 30.0)));
                float jitter = (lineNoise - 0.5) * _JitterAmount * _Intensity;

                float glitchLine = step(0.985, rand(float2(floor(uv.y * 35.0), floor(time * 8.0))));
                jitter += glitchLine * (rand(float2(time, uv.y)) - 0.5) * 0.08 * _Intensity;

                uv.x += jitter;

                float shift = _ColorShift * _Intensity;

                float r = tex2D(_MainTex, uv + float2(shift, 0)).r;
                float g = tex2D(_MainTex, uv).g;
                float b = tex2D(_MainTex, uv - float2(shift, 0)).b;

                fixed4 col = fixed4(r, g, b, 1);

                float noise = rand(uv * float2(640.0, 480.0) + time * 30.0);
                col.rgb += (noise - 0.5) * _NoiseAmount * _Intensity;

                float scanline = sin(uv.y * 900.0) * 0.5 + 0.5;
                col.rgb *= 1.0 - scanline * _ScanlineAmount * _Intensity;

                float2 center = uv - 0.5;
                float vignette = 1.0 - dot(center, center) * 1.2;
                col.rgb *= vignette;

                return col;
            }
            ENDCG
        }
    }
}