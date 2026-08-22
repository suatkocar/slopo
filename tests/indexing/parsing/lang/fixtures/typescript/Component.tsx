interface GreetingProps {
  name: string;
}

function Greeting({ name }: GreetingProps): JSX.Element {
  return <h1>Hello, {name}!</h1>;
}

const Farewell = ({ name }: GreetingProps): JSX.Element => {
  return <p>Goodbye, {name}!</p>;
};
