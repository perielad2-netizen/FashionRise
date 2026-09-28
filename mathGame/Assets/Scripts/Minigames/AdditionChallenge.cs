using System.Collections.Generic;
using UnityEngine;

namespace MathGame.Minigames
{
    [CreateAssetMenu(fileName = "AdditionChallenge", menuName = "MathGame/Addition Challenge")]
    public class AdditionChallenge : MathChallenge
    {
        [SerializeField] int left = 7;
        [SerializeField] int right = 5;
        [SerializeField] string[] answers = { "10", "11", "12", "13" };
        [SerializeField] int correctIndex = 2;

        public override string Prompt => left + " + " + right + " = ?";
        public override IReadOnlyList<string> Answers => answers;

        public override bool IsCorrect(int answerIndex)
        {
            return answerIndex == correctIndex;
        }
    }
}
