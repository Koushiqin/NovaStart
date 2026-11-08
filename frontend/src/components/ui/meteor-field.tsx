// 纯装饰层：登录/注册页流星背景（6 颗），prefers-reduced-motion 下由 CSS 整体隐藏
export default function MeteorField() {
  return (
    <div className="meteor-field" aria-hidden="true">
      {Array.from({ length: 6 }, (_, index) => (
        <span key={index} className="star" />
      ))}
    </div>
  )
}
