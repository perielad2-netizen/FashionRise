using System.Collections.Generic;
using UnityEngine;

namespace MathGame.Minigames
{
    public abstract class MathChallenge : ScriptableObject
    {
        public abstract string Prompt { get; }
        public abstract IReadOnlyList<string> Answers { get; }
        public abstract bool IsCorrect(int answerIndex);
    }
}
