const identity = <T,>(x: T): T => x;

const List = <T,>({ items }: { items: T[] }) => {
  return (
    <ul>
      <li>{items.length}</li>
    </ul>
  );
};
