// 🚀 We've started Quokka for you automatically on this file.
// 👀 Explore the code below to see some Quokka features in action.
// 🧪 Feel free to experiment and make changes as you go.

// ----- 📝 LOGGING -----

// See the output of console.log right next to your code
const quokka = { isAwesome: true, nodeVersion: process.version };

console.log(quokka);

// See the value of a variable simply by typing its name
quokka;

// Use breakpoints or special comments to inspect expressions
// without changing the code
const workingDir = process.cwd();

process.memoryUsage(); //?

// ----- 📊 COVERAGE -----

// Gutter indicators show what code was executed (code coverage)

// Orange indicators means only part of the line was executed
// because JavaScript stops processing after first false value
console.log('partialCoverage', false && true);

// Green indicators means that Quokka executed all statements
// on a line of code
if (false) {
  // White indicators means that a line of code was never
  // executed by Quokka
  console.log('noCoverage', true);
}

// ----- 🪲 TIME TRAVEL DEBUGGER -----

// Below is a simple example of some classes and functions.
// - 🔧 Press `Shift + F5`, or use `Quokka.js: Start Time Machine` command,
//   or click the debugger button in the Quokka panel,
//   to check out Quokka time travel debugger with interactive timeline.

{
  // Class definition for a simple Point in 2D space
  class Point {
    constructor(x, y) {
      this.x = x;
      this.y = y;
    }

    // Method to calculate the distance from another point
    distance(otherPoint) {
      const dx = this.x - otherPoint.x;
      const dy = this.y - otherPoint.y;
      return Math.sqrt(dx * dx + dy * dy);
    }

    // Method to move the point by a given amount
    move(dx, dy) {
      this.x += dx;
      this.y += dy;
    }
  }

  // Class definition for a Rectangle
  class Rectangle {
    constructor(width, height, position) {
      this.width = width;
      this.height = height;
      this.position = position; // position is a Point object
    }

    // Method to calculate the area of the rectangle
    area() {
      return this.width * this.height;
    }

    // Method to check if a point is inside the rectangle
    contains(point) {
      const withinX = point.x >= this.position.x && point.x <= this.position.x + this.width;
      const withinY = point.y >= this.position.y && point.y <= this.position.y + this.height;
      return withinX && withinY;
    }
  }

  // Function to create a random point
  function generateRandomPoint(maxX, maxY) {
    const x = Math.floor(Math.random() * maxX);
    const y = Math.floor(Math.random() * maxY);
    return new Point(x, y);
  }

  // Function to check if two rectangles overlap
  function rectanglesOverlap(rect1, rect2) {
    const overlapX =
      rect1.position.x < rect2.position.x + rect2.width && rect1.position.x + rect1.width > rect2.position.x;
    const overlapY =
      rect1.position.y < rect2.position.y + rect2.height && rect1.position.y + rect1.height > rect2.position.y;
    return overlapX && overlapY;
  }

  // Example usage
  const pointA = new Point(5, 10);
  const pointB = generateRandomPoint(100, 100);

  const rect1 = new Rectangle(50, 20, new Point(10, 10));
  const rect2 = new Rectangle(30, 30, new Point(40, 15));

  console.log({ msg: `Do rectangles overlap? ${rectanglesOverlap(rect1, rect2)}`, rect1, rect2 });
  console.log({ msg: `Is pointA inside rect1? ${rect1.contains(pointA)}`, rect1, pointA });
  console.log({ msg: `Distance between A and B: ${pointA.distance(pointB)}`, pointA, pointB });
}

// ----- 🚨 ERRORS -----

// Red indicators show where an error occurred. The error message
// is also shown beside the error
throw new Error('Kaboom! This is just a test error.');

// ----- 🌟 MUCH MORE -----

// There's a lot more Quokka can do! Visit our docs to learn more:
// - https://quokkajs.com/docs/

/* Quick Tips:
 *
 * To open a new Quokka scratch file:
 *   - 🔧 Press `Ctrl K, J` to create a new JavaScript File
 *   - 🔧 Press `Ctrl K, T` to create a new TypeScript File
 *   - 🔧 Press `Ctrl K, L` to open an interactive sample from:
 *     https://github.com/wallabyjs/interactive-examples
 *
 * To start/restart Quokka on an existing file:
 *   - 🔧 Press `Ctrl K, Q`
 *
 * To run code snippet in any file in your project:
 *   - 🔧 Type {{ in VS Code, the editor will automatically
 *        add the closing }} for you. Quokka then runs your
 *        code within these blocks, providing instant feedback.
 */
