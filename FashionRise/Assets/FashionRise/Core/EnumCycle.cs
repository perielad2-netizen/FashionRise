using System;

namespace FashionRise.Core
{
    public static class EnumCycle
    {
        public static T Next<T>(T value) where T : struct, Enum
        {
            var arr = (T[])Enum.GetValues(typeof(T));
            var i = Array.IndexOf(arr, value);
            return arr[(i + 1) % arr.Length];
        }
    }
}
