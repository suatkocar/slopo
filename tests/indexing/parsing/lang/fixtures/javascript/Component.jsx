function Greeting({ name }) {
  return <h1>Hello, {name}!</h1>;
}

const Card = ({ title, children }) => {
  return (
    <div className="card">
      <h2>{title}</h2>
      {children}
    </div>
  );
};
